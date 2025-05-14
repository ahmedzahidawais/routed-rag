from langchain_core.prompts import ChatPromptTemplate
from .logger import setup_logger
import time
from fastapi import HTTPException
import unicodedata
import asyncio
import json
from .utils import clean_source_text, split_multi_citations
from datetime import datetime, timezone

logger = setup_logger(__name__)


class RagPipeline:
    def __init__(self, llm, retriever, cross_encoder, container_client):
        self.llm = llm
        self.retriever = retriever
        self.cross_encoder = cross_encoder
        self.container_client = container_client
        self._setup_prompts()

    def _setup_prompts(self):
        """Initializes Langchain prompt templates."""
        # Verification Prompt (Simplified)
        self.verification_template = ChatPromptTemplate([
            ("system", "Du bist ein Informationsbewerter. Basierend NUR auf diesen Quellen:\n{context}\nKann die Frage '{query}' zumindest teilweise beantwortet werden? Antworte nur mit 'Ja' oder 'Nein'."),
        ])

        # Answer Generation Prompt
        self.answer_template = ChatPromptTemplate([
            ("system",
             "Du bist ein hilfreicher Assistent für deutschsprachige Nutzer. "
             "Beantworte die Frage NUR auf Basis der folgenden verifizierten Quellen:\n\n"
             "{context}\n\n"
             "Frage: {query}\n\n"
             "Anweisungen:\n"
             "1. Verwende NUR Informationen aus den angegebenen Quellen.\n"
             "2. Wenn die Quellen nicht ausreichend Informationen bieten, gib das offen zu ('Basierend auf den vorliegenden Quellen...').\n"
             "3. Zitiere die Quellen in deiner Antwort mit dem Format [1], [2], etc. (keine Listen wie [1, 2]).\n"
             "4. Antworte klar, präzise und ausschließlich auf Deutsch.\n"
             "5. Achte SEHR GENAU auf korrekte deutsche Grammatik, Rechtschreibung und Zeichensetzung, INSBESONDERE auf korrekte Leerzeichen.\n"
             "6. Sei hilfreich und freundlich.\n"
             "7. Vermeide Formulierungen wie 'Basierend auf dem Kontext …, Die Kontextinformationen …' oder ähnliche Aussagen.\n"
             "Antwort:"
             ),
            ("human", "{query}")
        ])


    async def _retrieve_documents(self, query: str, k: int = 5):
        """Retrieves initial documents using the vector store."""
        logger.info(f"Retrieving initial {k} documents for query: '{query[:50]}...'")
        start_time = time.time()
        try:
            initial_docs = self.retriever.get_relevant_documents(query)

            duration = time.time() - start_time
            logger.info(f"Retrieved {len(initial_docs)} documents in {duration:.2f}s")
            if not initial_docs:
                 logger.warning("No documents retrieved from vector store.")
            return initial_docs
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Fehler beim Abrufen relevanter Dokumente.")


    def _rerank_documents(self, query, docs, top_n=10, min_docs=5, relevance_threshold=0.1):
        """Reranks documents using CrossEncoder."""
        if not docs:
            return []

        logger.info(f"Reranking {len(docs)} documents...")
        start_time = time.time()
        try:
            document_pairs = [(query, doc.page_content) for doc in docs]
            relevance_scores = self.cross_encoder.predict(document_pairs, show_progress_bar=False)
            scored_docs = sorted(zip(docs, relevance_scores), key=lambda x: x[1], reverse=True)

            for i, (doc, score) in enumerate(scored_docs):
                 logger.debug(f"Doc {i+1}/{len(scored_docs)} | Score: {score:.4f} | Source: {doc.metadata.get('source', 'N/A')} | Preview: {doc.page_content[:80]}...")

            if scored_docs:
                filtered_docs = [doc for doc, score in scored_docs[:min_docs]]
                
                additional_docs = [doc for doc, score in scored_docs[min_docs:top_n] if score > relevance_threshold]
                filtered_docs.extend(additional_docs)

            duration = time.time() - start_time
            final_scores = [score for _, score in scored_docs[:len(filtered_docs)]]
            logger.info(f"Reranking finished in {duration:.2f}s. Selected {len(filtered_docs)} documents with scores: {[f'{s:.2f}' for s in final_scores]}")
            return filtered_docs

        except Exception as e:
            logger.error(f"Reranking failed: {e}. Falling back to initial retrieval order.", exc_info=True)
            return docs[:top_n] # Fallback

    def _prepare_context(self, docs):
        """Formats the final documents into a context string for the LLM and builds a citation map."""
        doc_contexts = []
        citation_map = {}
        for i, doc in enumerate(docs):
            citation_num = str(i + 1)
            cleaned_content = clean_source_text(doc.page_content)
            doc_context = f"[{citation_num}]: {cleaned_content}"
            doc_contexts.append(doc_context)
            citation_map[citation_num] = cleaned_content
        context = "\n\n".join(doc_contexts)
        logger.debug(f"Prepared context:\n{context[:200]}...")
        return context, citation_map

    async def _check_answerability(self, query: str, context: str) -> bool:
        """Uses LLM to check if the query can be answered from the context."""
        if not context:
            logger.warning("Cannot check answerability: Context is empty.")
            return False

        logger.info("Checking answerability...")
        start_time = time.time()
        try:
            verification_chain = self.verification_template | self.llm
            # Use ainvoke for single, non-streaming call
            response = await verification_chain.ainvoke({"context": context, "query": query})
            answer_text = response.content.strip().lower()
            duration = time.time() - start_time
            logger.debug(f"Answerability raw response: '{answer_text}' (took {duration:.2f}s)")

            is_answerable = "ja" in answer_text or "yes" in answer_text

            logger.info(f"Answerability check result: {is_answerable}")
            return is_answerable
        except Exception as e:
            logger.error(f"Answerability check failed: {e}. Assuming answerable.", exc_info=True)
            return True # Default to answerable on error to avoid blocking response

    async def generate_response(self, query: str, context: str, citation_map: dict):
        """Generates the final response using the LLM, streaming the output, and sends the citation map at the end."""
        logger.info("Generating final response stream...")
        start_time = time.time()
        response_buffer = ""
        try:
            generation_chain = self.answer_template | self.llm

            # Extract sources from context (now numeric)
            sources = list(citation_map.keys())

            # First, stream the main response
            async for chunk in generation_chain.astream({
                "context": context,
                "query": query,
                "source": ", ".join(sources) if sources else "Quelle"
            }):
                chunk_text = chunk.content
                if chunk_text:
                    chunk_text = split_multi_citations(chunk_text)
                    normalized_chunk = unicodedata.normalize('NFC', chunk_text)
                    response_buffer += normalized_chunk
                    yield normalized_chunk
                    await asyncio.sleep(0.04)

            

            # Send the citation map as a JSON string with a special marker
            citation_map_str = f"\n\nCITATION_MAP: {json.dumps(citation_map, ensure_ascii=False)}"
            yield citation_map_str
            response_buffer += citation_map_str

            duration = time.time() - start_time
            logger.info(f"Finished streaming response. Total generation time: {duration:.2f}s")
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"LLM streaming error after {duration:.2f}s: {e}", exc_info=True)
            if not response_buffer:
                yield "Es ist ein Fehler bei der Generierung der Antwort aufgetreten. Bitte versuchen Sie es erneut."
            else:
                pass

    async def _save_chat_log(self, query: str, response: str, context: str, duration: float):
        """Saves chat interaction to blob storage."""
        try:
            # Create a unique filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"chat_logs/chat_{timestamp}.json"
            
            # Prepare log data
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "query": query,
                "response": response,
                "context": context,
                "processing_time_seconds": duration,
                "model": self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown"
            }
            
            # Convert to JSON and upload
            log_json = json.dumps(log_data, ensure_ascii=False, indent=2)
            self.container_client.upload_blob(
                name=filename,
                data=log_json,
                overwrite=True
            )
            logger.info(f"Chat log saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save chat log: {e}", exc_info=True)

    async def process_chat(self, request):
        """Orchestrates the entire RAG pipeline for a chat request."""
        start_time_total = time.time()
        query = request.message.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein")

        logger.info(f"Processing request ID: {id(request)} | Query: '{query[:100]}...'")
        response_buffer = ""

        try:
            # 1. Retrieve
            initial_docs = await self._retrieve_documents(query)
            if not initial_docs:
                response = "Ich konnte leider keine relevanten Dokumente zu Ihrer Anfrage finden."
                yield response
                return

            # 2. Rerank
            reranked_docs = self._rerank_documents(query, initial_docs)
            if not reranked_docs:
                response = "Nach Prüfung der gefundenen Dokumente scheinen diese nicht relevant genug für Ihre Anfrage zu sein."
                yield response
                return

            # 3. Prepare Context and Citation Map
            context, citation_map = self._prepare_context(reranked_docs)

            # 4. Check Answerability
            is_answerable = await self._check_answerability(query, context)
            if not is_answerable:
                response = "Basierend auf den verfügbaren Informationen kann ich Ihre Frage leider nicht direkt beantworten. Vielleicht können Sie Ihre Frage umformulieren?"
                yield response
                return

            # 5. Generate Response Stream (with citation map)
            async for chunk in self.generate_response(query, context, citation_map):
                response_buffer += chunk
                yield chunk

            total_duration = time.time() - start_time_total
            logger.info(f"Request ID: {id(request)} | Successfully processed in {total_duration:.2f}s")

            # Save chat log after successful response
            await self._save_chat_log(query, response_buffer, context, total_duration)

        except HTTPException:
            raise
        except Exception as e:
            total_duration = time.time() - start_time_total
            logger.error(f"Request ID: {id(request)} | Unhandled exception during chat processing after {total_duration:.2f}s: {e}", exc_info=True)
            yield "Ein unerwarteter interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut."
