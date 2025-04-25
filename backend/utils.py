from io import BytesIO
import PyPDF2
from .logger import setup_logger
import unicodedata
import re

logger = setup_logger(__name__)


def extract_text_from_pdf(pdf_data: bytes, blob_name: str):
    """Extracts text from PDF byte data."""
    try:
        pdf_file = BytesIO(pdf_data)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"  # Add newline between pages
            except Exception as page_e:
                logger.warning(f"Could not extract text from page {i + 1} of {blob_name}: {page_e}")
        return text if text else None
    except PyPDF2.errors.PdfReadError as pdf_err:
        logger.error(f"Invalid PDF file {blob_name}: {pdf_err}")
        return None
    except Exception as e:
        logger.error(f"Error processing PDF content for {blob_name}: {e}", exc_info=True)
        return None


def clean_text(text: str) -> str:
    """Basic text cleaning."""
    text = unicodedata.normalize('NFC', text)  # Normalize unicode characters
    text = re.sub(r'\s+', ' ', text).strip()  # Collapse multiple whitespaces
    return text
