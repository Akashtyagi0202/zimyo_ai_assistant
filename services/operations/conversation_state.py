# services/conversation_state.py
"""
Redis-based conversation state management for HR actions
"""

import json
import redis
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def get_conversation_key(user_id: str, session_id: str) -> str:
    """Get Redis key for user's conversation state with session ID"""
    return f"conversation_state:{user_id}:{session_id}"

def get_user_sessions_key(user_id: str) -> str:
    """Get Redis key for user's session list"""
    return f"user_sessions:{user_id}"

def get_chat_history_key(user_id: str, session_id: str) -> str:
    """Get Redis key for chat history"""
    return f"chat_history:{user_id}:{session_id}"

def create_session(user_id: str, session_name: Optional[str] = None) -> str:
    """Create a new conversation session for user"""
    try:
        session_id = str(uuid.uuid4())[:8]  # Short unique ID
        timestamp = datetime.now().isoformat()

        session_info = {
            "session_id": session_id,
            "session_name": session_name or f"Session {session_id}",
            "created_at": timestamp,
            "last_active": timestamp,
            "status": "active"
        }

        # Add to user's session list
        sessions_key = get_user_sessions_key(user_id)
        sessions_raw = redis_client.get(sessions_key)
        sessions = json.loads(sessions_raw) if sessions_raw else []
        sessions.append(session_info)
        redis_client.setex(sessions_key, 86400, json.dumps(sessions))  # 24 hours

        logger.info(f"Created new session {session_id} for user {user_id}")
        return session_id
    except Exception as e:
        logger.error(f"Error creating session for {user_id}: {e}")
        return None

def get_user_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Get all sessions for a user"""
    try:
        sessions_key = get_user_sessions_key(user_id)
        sessions_raw = redis_client.get(sessions_key)

        if not sessions_raw:
            return []

        sessions = json.loads(sessions_raw)
        return sessions
    except Exception as e:
        logger.error(f"Error getting sessions for {user_id}: {e}")
        return []

def save_conversation_state(user_id: str, session_id: str, state: Dict[str, Any]) -> bool:
    """Save conversation state to Redis with session ID"""
    try:
        key = get_conversation_key(user_id, session_id)
        redis_client.setex(key, 1800, json.dumps(state))  # Expire in 30 minutes

        # Update session last_active timestamp
        update_session_activity(user_id, session_id)

        logger.info(f"Saved conversation state for user {user_id}, session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving conversation state for {user_id}, session {session_id}: {e}")
        return False

def get_conversation_state(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get conversation state from Redis with session ID"""
    try:
        key = get_conversation_key(user_id, session_id)
        logger.info(f"conversation key : {key}")
        state_raw = redis_client.get(key)

        if not state_raw:
            logger.info(f"No conversation state found for user {user_id}, session {session_id}")
            return None

        state = json.loads(state_raw)
        logger.info(f"Retrieved conversation state for user {user_id}, session {session_id}: {state.get('action', 'unknown')}")
        return state

    except Exception as e:
        logger.error(f"Error getting conversation state for {user_id}, session {session_id}: {e}")
        return None

def clear_conversation_state(user_id: str, session_id: str) -> bool:
    """Clear conversation state from Redis with session ID"""
    try:
        key = get_conversation_key(user_id, session_id)
        redis_client.delete(key)
        logger.info(f"Cleared conversation state for user {user_id}, session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing conversation state for {user_id}, session {session_id}: {e}")
        return False

def update_conversation_state(user_id: str, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update existing conversation state with new data"""
    try:
        current_state = get_conversation_state(user_id, session_id) or {}

        # Merge updates into current state
        for key, value in updates.items():
            # Deep merge for dictionaries (leave_info AND extracted_data)
            if key in ["leave_info", "extracted_data"] and isinstance(value, dict) and key in current_state:
                # Merge dictionaries - new values override old, but keep old values if not in new
                current_state[key].update(value)
                logger.debug(f"🔄 Merged {key}: {current_state[key]}")
            else:
                current_state[key] = value

        # Save updated state
        if save_conversation_state(user_id, session_id, current_state):
            return current_state
        else:
            return None

    except Exception as e:
        logger.error(f"Error updating conversation state for {user_id}, session {session_id}: {e}")
        return None

def update_session_activity(user_id: str, session_id: str) -> bool:
    """Update session's last activity timestamp"""
    try:
        sessions_key = get_user_sessions_key(user_id)
        sessions_raw = redis_client.get(sessions_key)

        if not sessions_raw:
            return False

        sessions = json.loads(sessions_raw)
        for session in sessions:
            if session.get("session_id") == session_id:
                session["last_active"] = datetime.now().isoformat()
                break

        redis_client.setex(sessions_key, 86400, json.dumps(sessions))
        return True
    except Exception as e:
        logger.error(f"Error updating session activity for {user_id}, session {session_id}: {e}")
        return False

def is_conversation_active(user_id: str, session_id: str) -> bool:
    """Check if user has an active conversation in specific session"""
    state = get_conversation_state(user_id, session_id)
    return state is not None and state.get("action") is not None

# Backward compatibility functions (for existing code)
def get_conversation_state_legacy(user_id: str) -> Optional[Dict[str, Any]]:
    """Legacy function - gets first active session or None"""
    sessions = get_user_sessions(user_id)
    if sessions:
        # Try to find active conversation in any session
        for session in sessions:
            session_id = session.get("session_id")
            state = get_conversation_state(user_id, session_id)
            if state and state.get("action"):
                return state
    return None

# Chat history management
def add_message_to_history(user_id: str, session_id: str, role: str, message: str) -> bool:
    """Add a message to chat history"""
    try:
        history_key = get_chat_history_key(user_id, session_id)
        history_raw = redis_client.get(history_key)
        history = json.loads(history_raw) if history_raw else []

        message_obj = {
            "role": role,  # 'user' or 'assistant'
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        history.append(message_obj)
        redis_client.setex(history_key, 86400, json.dumps(history))  # 24 hours

        logger.info(f"Added {role} message to history for user {user_id}, session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding message to history for {user_id}, session {session_id}: {e}")
        return False

def get_chat_history(user_id: str, session_id: str) -> List[Dict[str, Any]]:
    """Get chat history for a session"""
    try:
        history_key = get_chat_history_key(user_id, session_id)
        history_raw = redis_client.get(history_key)

        if not history_raw:
            logger.info(f"No chat history found for user {user_id}, session {session_id}")
            return []

        history = json.loads(history_raw)
        logger.info(f"Retrieved {len(history)} messages from history for user {user_id}, session {session_id}")
        return history
    except Exception as e:
        logger.error(f"Error getting chat history for {user_id}, session {session_id}: {e}")
        return []