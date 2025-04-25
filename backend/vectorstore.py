from .logger import setup_logger
import time
from .utils import extract_text_from_pdf, clean_text
from langchain_core.documents import Document
from azure.core.exceptions import AzureError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

logger = setup_logger(__name__)


class VectorStoreManager:
    def __init__(self, container_client, embedding_model, index_path):
        self.container_client = container_client
        self.embedding_model = embedding_model
        self.index_path = index_path
        self.vector_store = None
        self._load_or_create_index()

    def _load_pdf_docs_from_blob(self):
        """Loads and processes PDF documents from Azure Blob Storage."""
        start_time = time.time()
        logger.info("Starting PDF document loading from Azure Blob Storage...")
        blob_list = self.container_client.list_blobs()
        docs = []
        processed_files = 0
        failed_files = 0

        # Potential Speed Improvement: Use asyncio for parallel downloads if I/O bound
        # This requires making this function async and using an async blob client library or thread pool
        for blob in blob_list:
            if blob.name.endswith('.pdf'):
                logger.debug(f"Processing blob: {blob.name}")
                try:
                    blob_client = self.container_client.get_blob_client(blob.name)
                    blob_data = blob_client.download_blob(timeout=120).readall()

                    text = extract_text_from_pdf(blob_data, blob.name)
                    if text:
                        cleaned_text = clean_text(text)
                        docs.append(Document(page_content=cleaned_text, metadata={"source": blob.name}))
                        processed_files += 1
                    else:
                        logger.warning(f"No text extracted from {blob.name}")
                        failed_files += 1

                except AzureError as ae:
                    logger.error(f"Azure error downloading {blob.name}: {ae}")
                    failed_files += 1
                except Exception as e:
                    logger.error(f"Error processing blob {blob.name}: {e}", exc_info=True)
                    failed_files += 1

        duration = time.time() - start_time
        logger.info(f"Finished document loading. Processed: {processed_files}, Failed: {failed_files}. "
                    f"Duration: {duration:.2f}s")
        if not docs:
            raise ValueError("No processable PDF documents found in the container.")
        return docs

    def _create_and_save_index(self):
        """Creates the FAISS index from documents and saves it locally."""
        docs = self._load_pdf_docs_from_blob()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(docs)
        logger.info(f"Split {len(docs)} documents into {len(chunks)} chunks.")

        if not chunks:
            raise ValueError("Text splitting resulted in zero chunks.")

        logger.info("Creating FAISS vector store... This may take some time.")
        start_time = time.time()
        try:
            self.vector_store = FAISS.from_documents(
                documents=chunks,
                embedding=self.embedding_model
            )
            duration = time.time() - start_time
            logger.info(f"FAISS index created successfully. Duration: {duration:.2f}s")

            # Save the index locally
            self.vector_store.save_local(self.index_path)
            logger.info(f"FAISS index saved locally to: {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to create or save FAISS index: {e}", exc_info=True)
            raise RuntimeError(f"FAISS index creation failed: {e}") from e

    def _load_or_create_index(self):
        """Loads the FAISS index from local path or creates it if not found."""
        try:
            # Allowindex rebuild based on some condition if needed (e.g., env var, time check)
            rebuild_index = True  # Set to True to force rebuild
            if not rebuild_index and FAISS.exist_locally(self.index_path, self.embedding_model):
                logger.info(f"Loading existing FAISS index from: {self.index_path}")
                start_time = time.time()
                self.vector_store = FAISS.load_local(
                    self.index_path,
                    self.embedding_model,
                    allow_dangerous_deserialization=True
                )
                duration = time.time() - start_time
                logger.info(f"Successfully loaded FAISS index. Duration: {duration:.2f}s")
            else:
                logger.info(f"No existing index found at {self.index_path} or rebuild forced. Creating new index...")
                self._create_and_save_index()
        except Exception as e:
            logger.critical(f"Failed to load or create vector store: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize vector store: {e}")

    def get_retriever(self, k: int = 5):
        """Gets the vector store retriever."""
        if not self.vector_store:
            raise RuntimeError("Vector store is not initialized.")
        # Can configure search_type="mmr" (Maximal Marginal Relevance) for diversity
        return self.vector_store.as_retriever(search_kwargs={'k': k})
