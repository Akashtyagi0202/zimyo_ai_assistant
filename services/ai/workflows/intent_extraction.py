"""
Intent Extraction Node for LangGraph

Extracts user intent and data from messages using LangChain.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage

# Local imports
# Use existing working extractor (no LangChain dependency issues)
from services.ai.hrms_extractor import detect_intent_and_extract

logger = logging.getLogger(__name__)


def extract_intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract intent and data from user message.

    This node uses the LangChain-based intent extractor.

    Args:
        state: Current workflow state

    Returns:
        Updated state with intent and extracted_data
    """
    logger.info(f"🎯 Intent Extraction Node - User: {state['user_id']}")

    user_message = state.get("user_message", "")
    user_id = state.get("user_id")

    # Get previous context if available
    user_context = {
        "intent": state.get("intent", ""),
        "extracted_data": state.get("extracted_data", {})
    }

    # Get available leave types (from MCP or cache)
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.shared import get_leave_types_cached
        import asyncio

        mcp_client = get_http_mcp_client()

        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        available_leave_types = loop.run_until_complete(
            get_leave_types_cached(user_id, mcp_client)
        )
        loop.close()
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch leave types: {e}")
        available_leave_types = []

    # Extract intent using LangChain
    result = detect_intent_and_extract(
        user_message=user_message,
        user_context=user_context,
        available_leave_types=available_leave_types
    )

    logger.info(f"✅ Extracted intent: {result['intent']}, ready: {result.get('ready_to_execute', False)}")

    # Update state
    return {
        **state,
        "intent": result.get("intent", "unknown"),
        "extracted_data": result.get("extracted_data", {}),
        "ready_to_execute": result.get("ready_to_execute", False),
        "current_step": "intent_extracted",
        "messages": state.get("messages", []) + [HumanMessage(content=user_message)]
    }
