"""
LangChain Configuration for HRMS AI Assistant

This module centralizes all LangChain setup:
- LLM initialization (Gemini, OpenAI, DeepSeek)
- Memory management (Redis-based chat history)
- Prompt templates
- Output parsers
- Observability (LangSmith integration)

Author: Zimyo AI Team
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Config imports
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Model names
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
DEEPSEEK_MODEL = "deepseek-chat"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# LangSmith (for observability)
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "zimyo-hrms-assistant")

# Redis connection string
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# ============================================================================
# LLM INITIALIZATION
# ============================================================================

_llm_instance = None


def get_llm(temperature: float = 0.1, max_tokens: Optional[int] = None):
    """
    Get LangChain LLM instance based on LLM_PROVIDER.

    Uses singleton pattern for performance.

    Args:
        temperature: Model temperature (0.0-1.0). Default 0.1 for consistent extraction.
        max_tokens: Maximum tokens to generate. None = model default.

    Returns:
        LangChain LLM instance (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
    """
    global _llm_instance

    # Create new instance only if config changes
    if _llm_instance is None:
        if LLM_PROVIDER == "gemini":
            _llm_instance = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL,
                google_api_key=GEMINI_API_KEY,
                temperature=temperature,
                max_tokens=max_tokens or 2000,
                convert_system_message_to_human=True  # Gemini doesn't support system messages
            )
            logger.info(f"🤖 LangChain LLM: Google Gemini ({GEMINI_MODEL})")

        elif LLM_PROVIDER == "openai":
            _llm_instance = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=temperature,
                max_tokens=max_tokens or 500
            )
            logger.info(f"🤖 LangChain LLM: OpenAI ({OPENAI_MODEL})")

        elif LLM_PROVIDER == "deepseek":
            _llm_instance = ChatOpenAI(
                model=DEEPSEEK_MODEL,
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                temperature=temperature,
                max_tokens=max_tokens or 500
            )
            logger.info(f"🤖 LangChain LLM: DeepSeek ({DEEPSEEK_MODEL})")

        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")

    return _llm_instance


# ============================================================================
# MEMORY / SESSION MANAGEMENT
# ============================================================================

def get_session_history(user_id: str, session_id: str) -> BaseChatMessageHistory:
    """
    Get LangChain Redis-based chat message history for a user session.

    Args:
        user_id: User ID
        session_id: Session ID

    Returns:
        RedisChatMessageHistory instance
    """
    # Key format matches existing Redis structure for backward compatibility
    session_key = f"chat_history:{user_id}:{session_id}"

    return RedisChatMessageHistory(
        session_id=session_key,
        url=REDIS_URL,
        key_prefix="",  # No prefix since we're using full key in session_id
        ttl=86400  # 24 hours TTL (same as existing implementation)
    )


def create_conversational_chain(
    prompt: ChatPromptTemplate,
    llm = None,
    output_parser = None
):
    """
    Create a conversational chain with memory.

    Args:
        prompt: LangChain ChatPromptTemplate
        llm: LLM instance (defaults to get_llm())
        output_parser: Output parser (defaults to JsonOutputParser())

    Returns:
        RunnableWithMessageHistory chain with memory
    """
    llm = llm or get_llm()
    output_parser = output_parser or JsonOutputParser()

    # Create chain: prompt -> llm -> parser
    chain = prompt | llm | output_parser

    # Wrap with message history
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="user_message",
        history_messages_key="chat_history"
    )

    return chain_with_history


# ============================================================================
# OUTPUT PARSERS
# ============================================================================

def get_json_parser() -> JsonOutputParser:
    """
    Get JSON output parser for structured LLM responses.

    Returns:
        JsonOutputParser instance
    """
    return JsonOutputParser()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def enable_langsmith_tracing():
    """
    Enable LangSmith tracing for debugging and monitoring.

    Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env
    """
    if LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT
        logger.info(f"✅ LangSmith tracing enabled (Project: {LANGCHAIN_PROJECT})")
    else:
        logger.info("ℹ️ LangSmith tracing disabled")


# Auto-enable tracing on import
enable_langsmith_tracing()


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

def migrate_existing_session(user_id: str, session_id: str):
    """
    Migrate existing Redis session data to LangChain format.

    This preserves existing chat history when switching to LangChain.

    Args:
        user_id: User ID
        session_id: Session ID
    """
    import redis
    import json
    from langchain_core.messages import HumanMessage, AIMessage

    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )

    # Get old format history
    old_key = f"chat_history:{user_id}:{session_id}"
    old_history_raw = redis_client.get(old_key)

    if not old_history_raw:
        logger.info(f"No existing history for {user_id}:{session_id}")
        return

    try:
        old_history = json.loads(old_history_raw)

        # Get LangChain message history
        langchain_history = get_session_history(user_id, session_id)

        # Clear any existing messages
        langchain_history.clear()

        # Convert old format to LangChain messages
        for msg in old_history:
            role = msg.get("role")
            content = msg.get("message")

            if role == "user":
                langchain_history.add_message(HumanMessage(content=content))
            elif role == "assistant":
                langchain_history.add_message(AIMessage(content=content))

        logger.info(f"✅ Migrated {len(old_history)} messages for {user_id}:{session_id}")

    except Exception as e:
        logger.error(f"❌ Migration failed for {user_id}:{session_id}: {e}")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Simple LLM call
---------------------------
from services.ai.langchain_config import get_llm

llm = get_llm(temperature=0.7)
response = llm.invoke("Hello, how are you?")
print(response.content)


Example 2: Chain with prompt
-----------------------------
from services.ai.langchain_config import get_llm
from langchain_core.prompts import ChatPromptTemplate

llm = get_llm()
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant"),
    ("human", "{input}")
])

chain = prompt | llm
response = chain.invoke({"input": "Tell me a joke"})
print(response.content)


Example 3: Conversational chain with memory
--------------------------------------------
from services.ai.langchain_config import create_conversational_chain, get_llm
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{user_message}")
])

chain = create_conversational_chain(prompt)

# First message
response1 = chain.invoke(
    {"user_message": "My name is Akash"},
    config={"configurable": {"user_id": "240611", "session_id": "sess123"}}
)

# Second message (remembers context)
response2 = chain.invoke(
    {"user_message": "What's my name?"},
    config={"configurable": {"user_id": "240611", "session_id": "sess123"}}
)


Example 4: JSON output parsing
-------------------------------
from services.ai.langchain_config import get_llm, get_json_parser
from langchain_core.prompts import ChatPromptTemplate

llm = get_llm()
parser = get_json_parser()
prompt = ChatPromptTemplate.from_messages([
    ("human", "Extract person info from: {text}. Return JSON with name, age, city")
])

chain = prompt | llm | parser
result = chain.invoke({"text": "John is 25 years old and lives in Mumbai"})
print(result)  # {'name': 'John', 'age': 25, 'city': 'Mumbai'}


Example 5: Migrate existing session
------------------------------------
from services.ai.langchain_config import migrate_existing_session

migrate_existing_session("240611", "sess123")
"""
