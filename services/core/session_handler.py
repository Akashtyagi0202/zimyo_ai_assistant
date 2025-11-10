"""
Session Handler

Handles session management operations including:
- Retrieving user session data from Redis
- Creating new conversation sessions
- Getting user's conversation history
- Managing session metadata

This module keeps session-related logic separate from app.py routes.
"""

import logging
import json
from typing import Dict, Any, Optional

from services.operations.conversation_state import (
    create_session,
    get_user_sessions,
    get_chat_history
)

logger = logging.getLogger(__name__)


def get_user_session_data(redis_client, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user session data from Redis.

    Args:
        redis_client: Redis client instance
        user_id: User ID to retrieve session for

    Returns:
        Dictionary with user session data or None if not found
    """
    logger.debug(f"📦 Retrieving session for user {user_id}")

    user_data_raw = redis_client.get(user_id)
    if not user_data_raw:
        logger.warning(f"⚠️ No session found for user {user_id}")
        return None

    try:
        return json.loads(user_data_raw)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in session for user {user_id}: {e}")
        return None


def create_new_conversation_session(user_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new conversation session for a user.

    Args:
        user_id: User ID to create session for
        session_name: Optional name for the session

    Returns:
        Dictionary with session creation result:
        {
            "message": str,
            "sessionId": str,
            "sessionName": str
        }

    Raises:
        Exception: If session creation fails
    """
    logger.info(f"🆕 Creating new session for user {user_id}")

    session_id = create_session(user_id, session_name)

    if not session_id:
        raise Exception("Failed to create session")

    logger.info(f"✅ Session created: {session_id}")

    return {
        "message": "Session created successfully",
        "sessionId": session_id,
        "sessionName": session_name or f"Session {session_id}"
    }


def get_all_user_sessions(user_id: str) -> Dict[str, Any]:
    """
    Get all conversation sessions for a user.

    Args:
        user_id: User ID to get sessions for

    Returns:
        Dictionary with sessions list:
        {
            "userId": str,
            "sessions": list,
            "count": int
        }
    """
    logger.debug(f"📋 Fetching all sessions for user {user_id}")

    sessions = get_user_sessions(user_id)

    return {
        "userId": user_id,
        "sessions": sessions,
        "count": len(sessions)
    }


def get_session_chat_history(user_id: str, session_id: str) -> Dict[str, Any]:
    """
    Get chat history for a specific session.

    Args:
        user_id: User ID
        session_id: Session ID to get history for

    Returns:
        Dictionary with chat history:
        {
            "userId": str,
            "sessionId": str,
            "history": list,
            "count": int
        }
    """
    logger.debug(f"💬 Fetching chat history for user {user_id}, session {session_id}")

    history = get_chat_history(user_id, session_id)

    return {
        "userId": user_id,
        "sessionId": session_id,
        "history": history,
        "count": len(history)
    }
