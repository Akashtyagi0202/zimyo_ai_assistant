"""
AI-Powered HRMS Operation Handler

This module handles all HRMS operations using AI intelligence.
No hardcoded rules - everything is decided by AI.

Flow:
1. User sends message → AI understands intent
2. AI extracts information → Checks if complete
3. If complete → Execute operation
4. If incomplete → Ask user for missing info

Supported Operations:
- Leave applications
- Attendance marking (check-in/check-out)
- Leave balance queries
- HR policy questions

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional

# Import modular HRMS handlers
from .hrms_handlers import (
    handle_leave_balance,
    handle_attendance,
    handle_apply_leave,
    handle_apply_regularization,
    handle_apply_onduty,
    handle_get_holidays,
    handle_get_salary_slip
)
from .hrms_handlers.shared import get_leave_types_cached

logger = logging.getLogger(__name__)

# ============================================================================
# MAIN HANDLER - Entry point for all HRMS operations
# ============================================================================

async def handle_hrms_with_ai(
    user_id: str,
    user_message: str,
    session_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    🎯 MAIN ENTRY POINT: AI-powered HRMS operation handler

    FLOW:
    1. Load conversation history from Redis (context preservation)
    2. Get leave types from MCP (with 30min cache)
    3. AI analyzes message → extracts intent + data
    4. Merge with previous context (accumulation)
    5. Save back to Redis (for next message)
    6. Route to specific handler (leave/attendance/balance)

    HANDLES: Leave applications, attendance, balance queries
    AI FEATURES: Typo tolerance, multi-language, context-aware

    Args:
        user_id: Employee ID (e.g., "240611")
        user_message: User input (e.g., "apply sick leave for 22 nov")
        session_id: Conversation session ID (for multi-turn tracking)

    Returns:
        {"response": "...", "sessionId": "..."} - Response to user
        None - Policy question (pass to chat handler)

    Example:
        User: "apply leave"
        → Returns: {"response": "What type?", "sessionId": "..."}

        User: "sick"
        → Returns: {"response": "What date?", "sessionId": "..."}
    """
    # STEP 1: Load previous conversation data (if any)
    # This enables context accumulation across messages
    context = _get_conversation_context(user_id, session_id)

    # STEP 2: Get MCP client and leave types (cached for 30 min - performance optimization)
    from services.integration.mcp_client import get_http_mcp_client
    mcp_client = get_http_mcp_client()
    available_leave_types = await get_leave_types_cached(user_id, mcp_client)

    # STEP 3: AI analyzes user message
    # - Detects intent (apply_leave, mark_attendance, etc.)
    # - Extracts data (dates, types, reasons)
    # - Determines if ready to execute or needs more info
    ai_result = _analyze_with_ai(user_message, context, available_leave_types)

    # STEP 4: Merge AI output with previous context
    # Example: Previous {date: "22 nov"} + New {type: "sick"} = {date: "22 nov", type: "sick"}
    extracted_data = _merge_context(context, ai_result)

    # STEP 5: CRITICAL - Save merged data back to Redis
    # This ensures next message has accumulated context
    from services.operations.conversation_state import update_conversation_state

    update_conversation_state(user_id, session_id or "legacy", {
        "intent": ai_result.get("intent"),
        "extracted_data": extracted_data,  # Accumulated data!
        "available_leave_types": available_leave_types
    })

    logger.debug(f"💾 Context saved: {list(extracted_data.keys())}")

    # STEP 6: Route to appropriate handler
    # - apply_leave → _handle_apply_leave
    # - mark_attendance → _handle_attendance
    # - check_leave_balance → _handle_leave_balance
    # - policy_question → return None (fallback to chat)
    return await _route_to_handler(
        intent=ai_result.get("intent"),
        user_id=user_id,
        extracted_data=extracted_data,
        ready=ai_result.get("ready_to_execute", False),
        next_question=ai_result.get("next_question"),
        available_leave_types=available_leave_types,
        session_id=session_id
    )


# ============================================================================
# HELPER FUNCTIONS - Internal use only
# ============================================================================

def _get_conversation_context(user_id: str, session_id: Optional[str]) -> Dict:
    """
    📥 Load conversation context from Redis

    Returns previous extracted data (dates, types, reasons) from earlier messages.
    This enables multi-turn conversations where context accumulates.

    Returns:
        Dict with {intent, extracted_data, available_leave_types} or {}
    """
    from services.operations.conversation_state import get_conversation_state

    # Use "legacy" as default session_id to match the save behavior at line 100
    return get_conversation_state(user_id, session_id or "legacy") or {}


def _analyze_with_ai(
    user_message: str,
    context: Dict,
    leave_types: list
) -> Dict[str, Any]:
    """
    🧠 AI analyzes user message and extracts structured data

    Uses LLM (Gemini/OpenAI/DeepSeek) to:
    - Detect intent (what user wants)
    - Extract fields (dates, types, reasons)
    - Check if ready to execute
    - Generate follow-up question if needed

    Handles: Typos, mixed languages, shortcuts (SL/CL/EL)

    Returns:
        {
            "intent": "apply_leave"|"mark_attendance"|etc.,
            "extracted_data": {fields extracted from message},
            "missing_fields": [list of missing required fields],
            "next_question": "Question to ask user"|null,
            "ready_to_execute": true|false
        }
    """
    from services.ai.hrms_extractor import detect_intent_and_extract

    logger.info(f"🤖 Analyzing: '{user_message[:30]}...'")

    # Call AI model (temperature=0.1 for consistent extraction)
    result = detect_intent_and_extract(
        user_message=user_message,
        user_context=context,
        available_leave_types=leave_types
    )

    logger.info(f"✅ Intent: {result['intent']} | Ready: {result['ready_to_execute']}")

    return result


def _merge_context(old_context: Dict, ai_result: Dict) -> Dict:
    """
    🔄 Merge AI output with previous context (Context Accumulation)

    This is CRITICAL for multi-turn conversations:
    - Message 1: {date: "22 nov"}
    - Message 2: {type: "sick"}
    - Merged: {date: "22 nov", type: "sick"} ✓

    New values overwrite old if same key.
    Old values preserved if not in new data.

    Example:
        old_context = {"extracted_data": {"from_date": "2025-11-22"}}
        ai_result = {"extracted_data": {"leave_type": "Sick Leave"}}
        → Returns: {"from_date": "2025-11-22", "leave_type": "Sick Leave"}
    """
    merged = {
        **old_context.get("extracted_data", {}),  # Previous data
        **ai_result.get("extracted_data", {})      # New data
    }

    logger.debug(f"📦 Merged fields: {list(merged.keys())}")
    return merged


async def _route_to_handler(
    intent: str,
    user_id: str,
    extracted_data: Dict,
    ready: bool,
    next_question: str,
    available_leave_types: list,
    session_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Route to appropriate handler based on intent.

    Returns None for policy questions (handled by chat system).
    """
    from services.integration.mcp_client import get_http_mcp_client
    mcp_client = get_http_mcp_client()

    # Route based on intent
    if intent == "check_leave_balance":
        return await handle_leave_balance(user_id, mcp_client, session_id)

    elif intent == "mark_attendance":
        return await handle_attendance(
            user_id, extracted_data, ready, next_question,
            mcp_client, session_id
        )

    elif intent == "apply_leave":
        return await handle_apply_leave(
            user_id, extracted_data, ready, next_question,
            available_leave_types, mcp_client, session_id
        )

    elif intent == "apply_regularization":
        return await handle_apply_regularization(
            user_id, extracted_data, ready, next_question,
            mcp_client, session_id
        )

    elif intent == "apply_onduty":
        return await handle_apply_onduty(
            user_id, extracted_data, ready, next_question,
            mcp_client, session_id
        )

    elif intent == "get_holidays":
        return await handle_get_holidays(user_id, mcp_client, session_id)

    elif intent == "get_salary_slip":
        return await handle_get_salary_slip(user_id, mcp_client, session_id, {"values": extracted_data})

    elif intent == "policy_question":
        # Let regular chat handler process policy questions
        logger.info("📚 Routing to policy chat handler")
        return None

    else:
        # Unknown intent - DON'T return None, ask clarifying question!
        logger.warning(f"❓ Unknown intent: {intent}, asking for clarification")

        # NO NEED to save here - already saved at line 100!
        # Saving here would overwrite the correct intent

        return {
            "response": "मुझे समझ नहीं आया। क्या आप स्पष्ट कर सकते हैं? I didn't understand. Could you please clarify what you want to do? (e.g., apply leave, check attendance, view balance)",
            "sessionId": session_id
        }


# ============================================================================
# OPERATION HANDLERS
# ============================================================================
# Handlers are now modularized in services/operations/hrms_handlers/:
# - leave_balance.py - Query leave balance
# - attendance.py - Mark attendance (check-in/check-out)
# - apply_leave.py - Apply for leave
# - apply_regularization.py - Attendance regularization
#
# This structure allows easy addition of new handlers like:
# - on_duty.py - On-duty applications
# - calendar.py - Calendar booking with manager
# ============================================================================

# ============================================================================
# USAGE EXAMPLES (for developers)
# ============================================================================

"""
Example 1: Complete information in one message
----------------------------------------------
>>> result = await handle_hrms_with_ai(
...     user_id="240611",
...     user_message="apply sick leave for 4 nov health issues",
...     session_id="sess123"
... )
>>> print(result['response'])
✅ Leave applied successfully!
📋 Type: Sick Leave
📅 Dates: 2025-11-04 to 2025-11-04 (1 days)
📝 Reason: health issues


Example 2: Multi-message conversation
-------------------------------------
# Message 1
>>> result1 = await handle_hrms_with_ai("240611", "apply leave", "sess123")
>>> print(result1['response'])
किस प्रकार की छुट्टी? What type of leave?

# Message 2
>>> result2 = await handle_hrms_with_ai("240611", "casual", "sess123")
>>> print(result2['response'])
कब से? Start date?

# Message 3
>>> result3 = await handle_hrms_with_ai("240611", "12 nov", "sess123")
>>> print(result3['response'])
कारण? Reason?

# Message 4
>>> result4 = await handle_hrms_with_ai("240611", "personal work", "sess123")
>>> print(result4['response'])
✅ Leave applied successfully!


Example 3: Attendance
--------------------
>>> result = await handle_hrms_with_ai("240611", "punch in", "sess123")
>>> print(result['response'])
✅ CHECK-IN marked successfully at 09:30 AM


Example 4: Leave Balance
------------------------
>>> result = await handle_hrms_with_ai("240611", "leave balance", "sess123")
>>> print(result['response'])
📊 Your current leave balance:
• Sick Leave: 3.72 days
• Casual Leave: 2.72 days
"""
