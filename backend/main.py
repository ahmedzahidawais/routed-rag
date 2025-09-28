import asyncio
from typing import AsyncGenerator
from fastapi import HTTPException
from pydantic import BaseModel
from .services import (
    initialize_llm,
    initialize_embedding,
)
from .vectorstore import VectorStoreManager
from .ragpipeline import RagPipeline
from .logger import setup_logger
from config import CHROMA_DB_DIR

logger = setup_logger(__name__)


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str


try:
    logger.info("Starting application initialization...")
    llm = initialize_llm()
    embedding_model = initialize_embedding()
    container_client = None

    # Initialize Vector Store (Loads or Creates Index)
    vector_store_manager = VectorStoreManager(
        container_client=None,
        embedding_model=embedding_model,
        index_path=CHROMA_DB_DIR
    )
    # Force index build at startup so retriever is ready
    vector_store_manager.build_index(force=True)
    retriever = vector_store_manager.get_retriever(k=5)

    rag_pipeline_instance = RagPipeline(
        llm=llm,
        retriever=retriever,
        vector_manager=vector_store_manager
    )
    logger.info("Application components initialized successfully.")

except RuntimeError as init_err:
    logger.critical(f"APPLICATION STARTUP FAILED: {init_err}", exc_info=True)
    rag_pipeline_instance = None


async def process_chat_request(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
     Handles request processing and streams the response via RAG pipeline.
     This is intended to be called by the FastAPI endpoint.
     """
    # Use the globally initialized rag_pipeline_instance
    if rag_pipeline_instance is None:
        logger.error("Cannot process chat request: RAG pipeline failed to initialize.")
        # Yield a single error message and stop
        yield "Error: The chat service is currently unavailable due to an initialization problem."
        return
    # Optional: Check if retriever is available if it's critical
    if rag_pipeline_instance.retriever is None:
        logger.error("Cannot process chat request: Vector Store Retriever is unavailable.")
        yield "Error: The document search functionality is currently unavailable."
        return

    try:
        async for chunk in rag_pipeline_instance.process_chat(request):  # Call the method
            yield chunk
    except HTTPException as http_exc:
        logger.warning(f"HTTP Exception during chat processing: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Critical error during RAG pipeline processing: {e}", exc_info=True)
        yield "An unexpected error occurred while processing your request."
