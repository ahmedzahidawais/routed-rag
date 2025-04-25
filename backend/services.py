from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from .logger import setup_logger
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError
from sentence_transformers import CrossEncoder
from config import (AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT,
                    AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME)

logger = setup_logger(__name__)


def initialize_llm():
    try:
        # Initialize Azure OpenAI LLM
        llm = AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            deployment_name="gpt-4o-mini",
            api_version="2024-12-01-preview",
            streaming=True,
            temperature=0
        )
        logger.info("Successfully initialized Azure OpenAI LLM")
        return llm
    except Exception as e:
        logger.critical(f"Failed to initialize Azure OpenAI LLM: {e}", exc_info=True)
        raise RuntimeError(f"Could not initialize LLM: {e}")


def initialize_embedding():
    try:
        embedding_model = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            deployment="text-embedding-3-small",
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-02-01"
        )
        logger.info("Successfully initialized embedding model")
        return embedding_model
    except Exception as e:
        logger.critical(f"Failed to initialize Embedding Model: {e}", exc_info=True)
        raise RuntimeError(f"Could not initialize Embedding Model: {e}")


def initialize_blob_service():
    """Initializes and returns Azure Blob Service and Container clients."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        # Check if container exists (optional, but good practice)
        try:
            container_client.get_container_properties()
            logger.info("Successfully connected to Azure Blob Storage container: %s", CONTAINER_NAME)
        except AzureError as ae:
            logger.error(f"Container '{CONTAINER_NAME}' may not exist or is inaccessible: {ae}")
            raise RuntimeError(f"Container '{CONTAINER_NAME}' access error: {ae}") from ae
        return blob_service_client, container_client
    except Exception as e:
        logger.critical(f"Failed to connect to Azure Blob Storage: {e}", exc_info=True)
        raise RuntimeError(f"Could not connect to Blob Storage: {e}")


def initialize_cross_encoder():
    """Initializes and returns the CrossEncoder model."""
    try:
        cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        logger.info("Successfully initialized CrossEncoder model.")
        return cross_encoder
    except Exception as e:
        logger.critical(f"Failed to initialize CrossEncoder model: {e}", exc_info=True)
        raise RuntimeError(f"Could not initialize CrossEncoder: {e}")
