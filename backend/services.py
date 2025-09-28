from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .logger import setup_logger
from config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    OPENAI_EMBED_MODEL,
)

logger = setup_logger(__name__)


def initialize_llm():
    try:
        # Initialize OpenAI Chat LLM
        if not OPENAI_API_KEY:
            raise RuntimeError("Missing OPENAI_API_KEY")
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=OPENAI_CHAT_MODEL,
            streaming=True,
            temperature=0.3,
        )
        logger.info("Successfully initialized OpenAI Chat LLM")
        return llm
    except Exception as e:
        logger.critical(f"Failed to initialize OpenAI Chat LLM: {e}", exc_info=True)
        raise RuntimeError(f"Could not initialize LLM: {e}")


def initialize_embedding():
    try:
        if not OPENAI_API_KEY:
            raise RuntimeError("Missing OPENAI_API_KEY for embeddings")
        embedding_model = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY,
            model=OPENAI_EMBED_MODEL,
        )
        logger.info("Successfully initialized embedding model")
        return embedding_model
    except Exception as e:
        logger.critical(f"Failed to initialize Embedding Model: {e}", exc_info=True)
        raise RuntimeError(f"Could not initialize Embedding Model: {e}")
