from .logger import setup_logger
import time
from .utils import clean_source_text
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from typing import Tuple, Dict
import os
import requests
from config import GUTENBERG_BOOK_URL, CHROMA_DB_DIR

logger = setup_logger(__name__)


class VectorStoreManager:
    def __init__(self, container_client, embedding_model, index_path):
        self.embedding_model = embedding_model
        self.db_dir = CHROMA_DB_DIR
        self.vector_store = None
        self.chunks = []
        self._index_ready = False

    def _load_book_document(self) -> Document:
        """Downloads the Project Gutenberg book as a single Document."""
        logger.info(f"Downloading Gutenberg book from: {GUTENBERG_BOOK_URL}")
        resp = requests.get(GUTENBERG_BOOK_URL, timeout=60)
        resp.raise_for_status()
        text = resp.text
        cleaned = clean_source_text(text)
        return Document(page_content=cleaned, metadata={"source": GUTENBERG_BOOK_URL})

    def _load_text_from_gutenberg(self) -> Document:
        """Downloads a plain text book from Project Gutenberg as a single Document."""
        if not GUTENBERG_BOOK_URL:
            raise ValueError("GUTENBERG_BOOK_URL not configured")
        logger.info(f"Downloading Gutenberg book from: {GUTENBERG_BOOK_URL}")
        resp = requests.get(GUTENBERG_BOOK_URL, timeout=60)
        resp.raise_for_status()
        text = resp.text
        cleaned = clean_source_text(text)
        return Document(page_content=cleaned, metadata={"source": GUTENBERG_BOOK_URL})
    
    def _create_embeddings_for_batch(self, batch):
        """Adds a batch of documents to Chroma collection by embedding them."""
        if self.vector_store is None:
            raise RuntimeError("Vector store not initialized")
        self.vector_store.add_documents(batch)
        return True

    def _create_and_save_index(self):
        """Creates the persistent Chroma index from the book text."""
        book_doc = self._load_book_document()
        docs = [book_doc]

        # Simpler and cheaper splitter to reduce embedding volume and API pressure
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=120)
        self.chunks = splitter.split_documents(docs)
        logger.info(f"Split {len(docs)} documents into {len(self.chunks)} chunks using RecursiveCharacterTextSplitter.")
        if not self.chunks:
            raise ValueError("Text splitting resulted in zero chunks.")

        # Limit chunks to avoid large embedding costs in local/dev
        try:
            max_chunks = int(os.getenv("MAX_CHUNKS", "200"))
        except Exception:
            max_chunks = 200
        if max_chunks > 0 and len(self.chunks) > max_chunks:
            self.chunks = self.chunks[:max_chunks]
            logger.info(f"Limiting chunks to first {max_chunks} for indexing (dev-friendly).")

        logger.info("Creating Chroma vector store...")
        start_time = time.time()
        # Initialize persistent Chroma collection
        self.vector_store = Chroma(
            collection_name="book",
            embedding_function=self.embedding_model,
            persist_directory=self.db_dir,
        )
        # Add in batches
        batch_size = 32
        for i in range(0, len(self.chunks), batch_size):
            batch = self.chunks[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} with {len(batch)} chunks.")
            self._create_embeddings_for_batch(batch)
            time.sleep(0.05)

        self.vector_store.persist()
        duration = time.time() - start_time
        logger.info(f"Chroma index created successfully. Duration: {duration:.2f}s")
        self._index_ready = True

    def build_index(self, force: bool = True):
        """Build the index at startup. If force is False, load if present; otherwise create."""
        rebuild_env = os.getenv("REBUILD_INDEX", "false").lower() == "true"
        force_rebuild = force or rebuild_env
        has_existing = os.path.isdir(self.db_dir) and os.listdir(self.db_dir)
        if not force_rebuild and has_existing:
            logger.info(f"Loading existing Chroma index from: {self.db_dir}")
            self.vector_store = Chroma(
                collection_name="book",
                embedding_function=self.embedding_model,
                persist_directory=self.db_dir,
            )
            self._index_ready = True
        else:
            logger.info("Building Chroma index now (forced rebuild or missing index)...")
            self._create_and_save_index()
        
    # Keyword retriever removed for simplicity

    def get_retriever(self, k: int = 10):
        """Gets the ensemble retriever combining keyword and vector search."""
        if not self.vector_store:
            raise RuntimeError("Vector store not initialized. Ensure build_index(force=True) was called at startup.")

        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={'k': k}
        )
    
    # Context preparation with citations removed in simplified app
