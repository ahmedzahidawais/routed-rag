from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .main import process_chat_request, ChatRequest
from .logger import setup_logger

logger = setup_logger(__name__)

app = FastAPI(
    title="RAG Chatbot API",
    description="API endpoint for the Retrieval-Augmented Generation Chatbot",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def get_chatbot_response(request: ChatRequest):
    """
    Endpoint to receive a user message and stream back the chatbot's response.
    """
    logger.info(f"Received chat request: {request.message[:50]}...")  # Log request in endpoint
    try:
        # Return a StreamingResponse using the async generator from main.py
        return StreamingResponse(
            process_chat_request(request),
            media_type="text/event-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up stream in /chat endpoint: {e}", exc_info=True)
        # Raise a generic 500 error
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Health and liveness endpoints
@app.get("/health", tags=["Health"])
async def health_probe(response: Response):
    response.status_code = 200
    return {"status": "ok", "detail": "Service is healthy"}

@app.get("/liveness", tags=["Health"])
async def liveness_probe(response: Response):
    response.status_code = 200
    return {"status": "alive", "detail": "Service is live"}
