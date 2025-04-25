import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Now, fetch your keys from the environment

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH")

if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_STORAGE_CONNECTION_STRING]):
    raise ValueError("One or more environment variables are missing.")
