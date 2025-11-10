# app.py
"""
FastAPI Application - Routing Layer Only

This module defines API routes and delegates all business logic
to specialized handler modules in services/.

Routes:
- POST /login → services.core.login_handler
- POST /chat → services.operations.handlers
- Session management → services.core.session_handler
"""

import logging
import json
import redis
import re
from typing import Optional, Dict
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Import handlers (business logic is in these modules)
from services.core.login_handler import handle_login
from services.core.session_handler import (
    get_user_session_data,
    create_new_conversation_session,
    get_all_user_sessions,
    get_session_chat_history
)
from services.operations.conversation_state import add_message_to_history
# -----------------------------
# FastAPI app & logger
# -----------------------------
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
logger.info(f"Loaded Embedding Model: {embedding_model}")
# Redis connection
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# -----------------------------
# Models
# -----------------------------
class Message(BaseModel):
    userId: str
    message: str
    sessionId: Optional[str] = None
    context: Optional[Dict] = None

class SessionRequest(BaseModel):
    userId: str
    sessionName: Optional[str] = None

# -----------------------------
# Login API
# -----------------------------
@app.post("/login")
async def login(userId: str = Query(...), role: str = Query(...), userToken: str = Query(...)):
    """
    User login endpoint - delegates to login_handler

    Validates user credentials and creates session with:
    - User data from Zimyo API
    - Processed policy documents
    - Generated embeddings for semantic search
    """
    try:
        result = await handle_login(
            user_id=userId,
            role=role,
            user_token=userToken,
            redis_client=redis_client,
            embedding_model=embedding_model
        )
        return result

    except Exception as e:
        logger.exception(f"❌ Login failed for user {userId}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during login: {str(e)}"
        )

# -----------------------------
# Get session API
# -----------------------------
@app.get("/session/{userId}")
def get_user_session(userId: str):
    """
    Get user session data from Redis

    Returns user info, policies, and embeddings
    """
    session_data = get_user_session_data(redis_client, userId)

    if not session_data:
        return {"message": f"No session found for userId: {userId}"}

    return session_data

# -----------------------------
# Chat API - Clean and Optimized
# -----------------------------
@app.post("/chat")
async def chat(message: Message):
    """
    Clean chat API that only handles user validation and routing
    All business logic moved to separate operation handlers
    """
    user_id = message.userId
    user_prompt = message.message.strip()
    session_id = message.sessionId
    conversation_context = message.context

    # User validation and session retrieval
    try:
        user_data_raw = redis_client.get(user_id)
        if not user_data_raw:
            raise HTTPException(status_code=404, detail="User not logged in. Please login first.")

        user_data = json.loads(user_data_raw)
        user_role = user_data["role"]
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON data for user {user_id}")
        raise HTTPException(status_code=500, detail="Invalid user session data")
    except KeyError as e:
        logger.error(f"Missing key in user data for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Incomplete user session data")

    # Basic input validation
    if not user_prompt or len(user_prompt.strip()) == 0:
        response_data = {"response": "Please provide a valid message."}
        if session_id:
            response_data["sessionId"] = session_id
        return response_data

    # Log request
    logger.info("Processing message for user_id=%s, role=%s, length=%d chars", user_id, user_role, len(user_prompt))

    # Route to operation handler
    try:
        from services.operations.handlers import handle_user_operation

        result = await handle_user_operation(
            redis_client=redis_client,
            user_id=user_id,
            user_prompt=user_prompt,
            user_role=user_role,
            session_id=session_id,
            conversation_context=conversation_context
        )

        # Add manager-specific formatting if needed
        if user_role == "manager" and result.get("response") and not result.get("description"):
            try:
                from services.ai.chat import create_description
                response_text = result["response"]
                if "Description:" in response_text:
                    q_type = response_text.split("Description:")[-1].strip()
                    q_type = re.sub(r"[^a-zA-Z0-9 ]", "", q_type).strip()
                else:
                    q_type = create_description(user_prompt)
                result["description"] = q_type
            except Exception as e:
                logger.error(f"Error adding manager description: {e}")

        # Save messages to chat history if session_id is provided
        if session_id:
            try:
                add_message_to_history(user_id, session_id, "user", user_prompt)
                if result.get("response"):
                    add_message_to_history(user_id, session_id, "assistant", result["response"])
            except Exception as e:
                logger.error(f"Error saving messages to history: {e}")

        return result

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        error_response = {"response": "I'm sorry, I encountered an error processing your request. Please try again."}
        if session_id:
            error_response["sessionId"] = session_id
        return error_response

# -----------------------------
# Session Management APIs
# -----------------------------
@app.post("/sessions/create")
def create_new_session(request: SessionRequest):
    """
    Create a new conversation session for user

    Delegates to session_handler for business logic
    """
    try:
        result = create_new_conversation_session(
            user_id=request.userId,
            session_name=request.sessionName
        )
        return result

    except Exception as e:
        logger.exception(f"❌ Failed to create session for {request.userId}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.get("/sessions/{userId}")
def get_sessions(userId: str):
    """
    Get all conversation sessions for a user

    Delegates to session_handler for business logic
    """
    return get_all_user_sessions(userId)


@app.get("/sessions/{userId}/{sessionId}/history")
def get_session_history(userId: str, sessionId: str):
    """
    Get chat history for a specific session

    Delegates to session_handler for business logic
    """
    return get_session_chat_history(userId, sessionId)

@app.get("/")
def root():
    """Serve the test interface"""
    return FileResponse('static/index.html')

@app.get("/api")
def api_root():
    """API status endpoint"""
    return {"message": "Zimyo AI Assistant API is running"}

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------
# Run app
# -----------------------------
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
