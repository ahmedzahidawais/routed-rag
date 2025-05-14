from .logger import setup_logger
import re
import fitz  # PyMuPDF

logger = setup_logger(__name__)

def extract_pdf_blocks(pdf_data: bytes, blob_name: str):
    """
    Extract text blocks from a PDF byte stream using PyMuPDF.

    This function extracts text from a PDF provided as a byte stream (e.g., from Azure Blob Storage)
    and returns it as a list of text blocks, where each block typically corresponds to a paragraph
    or section. This format is suitable for downstream tasks in a RAG (Retrieval-Augmented Generation)
    pipeline, as it preserves semantic units that can be indexed and retrieved efficiently.

    Args:
        pdf_data (bytes): Byte stream of the PDF file.
        blob_name (str): Name of the blob for logging purposes.

    Returns:
        List[str]: A list of text blocks extracted from the PDF.

    Raises:
        fitz.FileDataError: If the PDF data is corrupted or invalid.
        Exception: For other unexpected errors during processing.
    """
    blocks = []
    try:
        # Open the PDF document from byte stream
        doc = fitz.open("pdf", pdf_data)
        
        # Iterate through each page in the PDF
        for page in doc:
            # Get text blocks from the current page
            page_blocks = page.get_text("blocks")
            
            # For each block, extract the text and strip whitespace
            for block in page_blocks:
                text = block[4].strip()  # block[4] contains the text of the block
                if text:  # Ensure the block is not empty
                    blocks.append(text)
        
        # Close the PDF document
        doc.close()
        
    except fitz.FileDataError as e:
        logger.error(f"Invalid or corrupted PDF data in {blob_name}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error extracting text from {blob_name}: {e}", exc_info=True)
        raise
    
    if not blocks:
        logger.warning(f"No text blocks extracted from {blob_name}")
    
    return blocks

def clean_source_text(text: str) -> str:
    """Enhanced text cleaning for RAG applications."""
    if not text:
        return ""

    # Normalize unicode characters

    # Remove repetitive page footers
    text = re.sub(r"Angebotsnummer 2025-12494 vom 16\.03\.2025 Seite \d+ von 224", "", text)

    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    # Replace multiple newlines with a placeholder
    text = re.sub(r'\n{2,}', '<<<PARA>>>', text)
    # Replace remaining single newlines (line wraps) with a space
    text = re.sub(r'\n', ' ', text)
    # Restore paragraph breaks
    text = re.sub(r'<<<PARA>>>', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def split_multi_citations(text):
    # Replace [2, 4] with [2][4]
    return re.sub(r'\[(\d+(?:,\s*\d+)+)\]', lambda m: ''.join(f'[{n.strip()}]' for n in m.group(1).split(',')), text)