from langchain_core.prompts import ChatPromptTemplate
from .logger import setup_logger
import time
from fastapi import HTTPException
import json
from datetime import datetime, timezone
from .weather import WeatherClient
import os

logger = setup_logger(__name__)


class RagPipeline:
    def __init__(self, llm, retriever, vector_manager=None):
        self.llm = llm
        self.retriever = retriever
        self.weather_client = WeatherClient()
        self.vector_manager = vector_manager
        self._setup_prompts()

    def _setup_prompts(self):
        """Initializes Langchain prompt templates."""
        self.answer_template = ChatPromptTemplate([
            ("system",
             "You are a helpful assistant. Answer the user's question using the provided context when relevant. "
             "If the context does not help, still answer concisely based on your general knowledge. "
             "Keep answers short and clear.\n\nContext:\n{context}"),
            ("human", "Question: {query}")
        ])


    async def _retrieve_documents(self, query: str):
        """Retrieves documents using the vector store (simple similarity)."""
        logger.info(f"Retrieving initial documents for query: '{query[:50]}...'")
        start_time = time.time()
        try:
            retriever = None
            if self.vector_manager is not None:
                try:
                    retriever = self.vector_manager.get_retriever(k=5)
                except Exception:
                    retriever = None
            if retriever is None:
                retriever = self.retriever
            initial_docs = retriever.get_relevant_documents(query)

            duration = time.time() - start_time
            logger.info(f"Retrieved {len(initial_docs)} documents in {duration:.2f}s")
            if not initial_docs:
                 logger.warning("No documents retrieved from vector store.")
            return initial_docs
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve relevant documents.")


    async def _save_chat_log(self, query: str, response: str, context: str, duration: float):
        """Saves chat interaction to local file storage."""
        try:
            
            os.makedirs("chat_logs", exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = os.path.join("chat_logs", f"chat_{timestamp}.json")

            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "query": query,
                "response": response,
                "context": context,
                "processing_time_seconds": duration,
                "model": getattr(self.llm, 'model', getattr(self.llm, 'model_name', 'unknown')),
            }

            with open(filename, "w", encoding="utf-8") as f:
                f.write(json.dumps(log_data, ensure_ascii=False, indent=2))
            logger.info(f"Chat log saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save chat log: {e}", exc_info=True)

    async def process_chat(self, request):
        """Orchestrates the entire RAG pipeline for a chat request."""
        start_time_total = time.time()
        query = request.message.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Message must not be empty")

        logger.info(f"Processing request ID: {id(request)} | Query: '{query[:100]}...'")
        response_buffer = ""

        try:
            router = ChatPromptTemplate([
                ("system", "You are a router. Reply with exactly one token: weather | rag | both. "
                           "Choose 'both' if the user asks about places from the book and also current conditions."),
                ("human", "Question: {query}")
            ]) | self.llm
            try:
                r = await router.ainvoke({"query": query})
                label = (r.content or "").strip().lower()
                if "both" in label:
                    decision = {"use_weather": True, "use_retriever": True}
                elif "weather" in label:
                    decision = {"use_weather": True, "use_retriever": False}
                elif "rag" in label:
                    decision = {"use_weather": False, "use_retriever": True}
                else:
                    raise ValueError("Unrecognized label")
            except Exception:
                lowered = query.lower()
                decision = {"use_weather": any(k in lowered for k in ["weather","forecast","temperature","rain","wind","humid","snow"]), "use_retriever": True}

            weather_text = ""
            if decision.get("use_weather"):
                try:
                    weather_text, _ = await self.weather_client.get_weather_answer(query)
                except Exception:
                    weather_text = ""

            rag_context = ""
            places: list[str] = []
            if decision.get("use_retriever"):
                docs = await self._retrieve_documents(query)
                if docs:
                    rag_context = "\n\n".join([d.page_content for d in docs])
                    extract_places = ChatPromptTemplate([
                        ("system", "Extract a JSON array of up to 5 Italian city names mentioned in the context that relate to Mark Twain's travels. Reply with only JSON array, e.g., [\"Rome\", \"Florence\"]. If none, reply []."),
                        ("human", "Context:\n{ctx}")
                    ]) | self.llm
                    try:
                        resp = await extract_places.ainvoke({"ctx": rag_context[:6000]})
                        parsed = json.loads((resp.content or "[]").strip())
                        if isinstance(parsed, list):
                            places = [str(p) for p in parsed][:5]
                    except Exception:
                        places = []

            # If both: fetch weather for extracted places and add to weather_text
            if decision.get("use_weather") and places:
                lines = []
                for p in places:
                    try:
                        line = await self.weather_client.get_weather_for_city(p)
                        lines.append(line)
                    except Exception:
                        continue
                if lines:
                    weather_text = (weather_text + "\n\n" if weather_text else "") + "\n".join(lines)

            compose = ChatPromptTemplate([
                ("system", "You are a helpful assistant. If weather facts are provided, include them. If document context is provided, summarize the places and relevant details briefly. Keep the final answer concise and useful."),
                ("human", "Question: {query}\n\nWeather facts (optional):\n{weather}\n\nDocument context (optional):\n{context}")
            ]) | self.llm

            async for chunk in compose.astream({"query": query, "weather": weather_text, "context": rag_context}):
                text = chunk.content
                if text:
                    response_buffer += text
                    yield text

            total_duration = time.time() - start_time_total
            logger.info(f"Request ID: {id(request)} | Successfully processed in {total_duration:.2f}s")

            # Save chat log after successful response
            context_for_log = ""
            await self._save_chat_log(query, response_buffer, context_for_log, total_duration)

        except HTTPException:
            raise
        except Exception as e:
            total_duration = time.time() - start_time_total
            logger.error(f"Request ID: {id(request)} | Unhandled exception during chat processing after {total_duration:.2f}s: {e}", exc_info=True)
            yield "An unexpected internal error occurred. Please try again later."
