# RAGChatbot – Assignment Adaptation (OpenAI + Chroma)

This project now solves the case study from the provided home assignment:

- Answers book questions using a RAG index. By default, it ingests Mark Twain's "The Innocents Abroad" from Project Gutenberg.
- Answers weather questions by calling OpenWeatherMap (geocoding + current weather) and streams a short answer with a citation map.

## Configuration

Create a `.env` file in the project root with the following variables as needed (see `.env.example`):

```
# OpenAI (non-Azure)
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

# Chroma (persistent local store)
CHROMA_DB_DIR=chroma_db

# Assignment specifics
GUTENBERG_BOOK_URL=https://www.gutenberg.org/cache/epub/3176/pg3176.txt
OPENWEATHERMAP_API_KEY=
USE_GUTENBERG=true
```

The app downloads and indexes the book from the given URL on first start. Chroma persists the index in `CHROMA_DB_DIR`.

## Run locally

1. Backend: `uvicorn backend.app:app --reload`
2. Frontend: in `frontend/` run `npm install && npm run dev`

## Docker (one command)

1. Copy `.env.example` to `.env` and fill `OPENAI_API_KEY` (and `OPENWEATHERMAP_API_KEY` if you want weather):
   - Windows PowerShell: `cp .env.example .env`
2. Build and run:
   - `docker compose up --build`
3. Open:
   - Backend: `http://localhost:8000/docs`
   - Frontend: `http://localhost:5173`

## Example queries

- Weather: "What's the weather in Paris?"
- Book: "What did Mark Twain say about the Sphinx?"
- Mixed intent: "I'm visiting Rome soon; what's the weather like there now?"

## Notes

- The code uses LangChain for prompts, retrieval, and FAISS management; weather calls are simple HTTP requests.