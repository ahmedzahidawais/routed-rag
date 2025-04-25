import asyncio
from typing import AsyncGenerator
from fastapi import HTTPException
from pydantic import BaseModel
from .services import (
    initialize_llm,
    initialize_embedding,
    initialize_blob_service,
    initialize_cross_encoder
)
from .vectorstore import VectorStoreManager
from .ragpipeline import RagPipeline
from .logger import setup_logger
from config import FAISS_INDEX_PATH

logger = setup_logger(__name__)


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str


try:
    logger.info("Starting application initialization...")
    llm = initialize_llm()
    embedding_model = initialize_embedding()
    blob_service_client, container_client = initialize_blob_service()
    cross_encoder = initialize_cross_encoder()

    # Initialize Vector Store (Loads or Creates Index)
    vector_store_manager = VectorStoreManager(
        container_client=container_client,
        embedding_model=embedding_model,
        index_path=FAISS_INDEX_PATH
    )
    retriever = vector_store_manager.get_retriever(k=5)

    rag_pipeline_instance = RagPipeline(
        llm=llm,
        retriever=retriever,
        cross_encoder=cross_encoder,
        container_client=container_client
    )
    logger.info("Application components initialized successfully.")

except RuntimeError as init_err:
    logger.critical(f"APPLICATION STARTUP FAILED: {init_err}", exc_info=True)
    rag_pipeline_instance = None


# --- Core Chat Processing Function ---
# This is the function app.py will call
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
        # Stream the response directly from the pipeline instance's method
        async for chunk in rag_pipeline_instance.process_chat(request):  # Call the method
            yield chunk
    except HTTPException as http_exc:
        logger.warning(f"HTTP Exception during chat processing: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Critical error during RAG pipeline processing: {e}", exc_info=True)
        yield "An unexpected error occurred while processing your request."
