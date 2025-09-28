from .logger import setup_logger
import re
import unicodedata

logger = setup_logger(__name__)


def clean_source_text(text: str) -> str:
    """Enhanced text cleaning for RAG, preserving table Markdown."""
    if not text:
        return ""

    # Normalize unicode (e.g., smart quotes, German umlauts)
    text = unicodedata.normalize('NFKD', text)

    # Remove specific repetitive footers (customize based on doc)
    text = re.sub(r"Vertraulich\. Alle Rechte vorbehalten\..*?© Volkswagen Aktiengesellschaft", "", text, flags=re.DOTALL)
    text = re.sub(r"CONFIDENTIAL", "", text)
    text = re.sub(r"Produktionsmode Querschnittslastenheft LAH.DUM.907.AS Seite \d+ von 40", "", text)

    lines = text.split('\n')
    cleaned_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') or in_table:
            in_table = True 
            cleaned_lines.append(line.rstrip())
        else:
            in_table = False
            if stripped:
                cleaned_lines.append(stripped)
    
    text = '\n'.join(cleaned_lines)

    text = re.sub(r'\n{2,}', '<<<PARA>>>', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'<<<PARA>>>', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()

def split_multi_citations(text):
    # Replace [2, 4] with [2][4]
    return re.sub(r'\[(\d+(?:,\s*\d+)+)\]', lambda m: ''.join(f'[{n.strip()}]' for n in m.group(1).split(',')), text)