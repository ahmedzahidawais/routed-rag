import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

# Persistent local vector store (Chroma)
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", os.path.join("chroma_db"))

# Assignment-specific config
GUTENBERG_BOOK_URL = os.getenv(
    "GUTENBERG_BOOK_URL",
    # Mark Twain - The Innocents Abroad (Project Gutenberg plain text)
    "https://www.gutenberg.org/cache/epub/3176/pg3176.txt",
)

OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

