"""
Apply Regularization Handler

Handles attendance regularization requests.
User asks: "apply regularization for 6 oct from 9:30 to 18:30 forgot to punch"
Response: Validates, applies regularization, and confirms with details
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .shared import RESPONSE_TEMPLATES

logger = logging.getLogger(__name__)


async def handle_apply_regularization(
    user_id: str,
    extracted_data: Dict,
    ready_to_execute: bool,
    next_question: str,
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle attendance regularization application.

    User wants to regularize attendance for missed punch-in/out.
    May take multiple messages to collect:
    - Date
    - From time (check-in time)
    - To time (check-out time)
    - Reason

    Example conversation:
        User: "apply regularization"
        Bot: "Which date do you want to regularize?"

        User: "6 oct"
        Bot: "What was your check-in time?"

        User: "9:30 am"
        Bot: "What was your check-out time?"

        User: "6:30 pm"
        Bot: "What's the reason for regularization?"

        User: "forgot to punch"
        Bot: "✅ Regularization applied successfully!"

    Example output:
        ✅ छुट्टी सफलतापूर्वक लागू हो गई! Regularization applied successfully!

        📅 Date: 2025-10-06
        🕐 Time: 09:30 to 18:30 (9 hours)
        📝 Reason: forgot to punch in/out

    Args:
        user_id: Employee ID
        extracted_data: Dictionary with date, from_time, to_time, reason
        ready_to_execute: Whether all required info is present
        next_question: Question to ask if info incomplete
        mcp_client: MCP client instance
        session_id: Session ID for conversation tracking

    Returns:
        Response dictionary with regularization application result
    """
    from services.operations.conversation_state import clear_conversation_state

    # If not ready, ask question (state already saved in handle_hrms_with_ai)
    if not ready_to_execute:
        logger.info(f"⏳ Regularization info incomplete, asking user")
        return {
            "response": next_question,
            "sessionId": session_id
        }

    # Ready to execute
    logger.info(f"✅ Applying regularization for user {user_id}")

    # Extract and format date/time
    date = extracted_data.get("date")
    from_time = extracted_data.get("from_time")
    to_time = extracted_data.get("to_time")
    reason = extracted_data.get("reason", "forgot to punch in/out")

    # Format datetime strings for API (YYYY-MM-DD HH:mm)
    from_datetime = f"{date} {from_time}"
    to_datetime = f"{date} {to_time}"

    # Calculate total hours (optional, API has default)
    try:
        from_dt = datetime.strptime(from_datetime, "%Y-%m-%d %H:%M")
        to_dt = datetime.strptime(to_datetime, "%Y-%m-%d %H:%M")
        diff = to_dt - from_dt
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        total_hours = f"{hours:02d}:{minutes:02d}:00"
    except Exception as e:
        logger.warning(f"Could not calculate hours: {e}, using default")
        total_hours = "09:00:00"

    # Apply regularization
    result = await mcp_client.call_tool("apply_regularization", {
        "user_id": user_id,
        "from_datetime": from_datetime,
        "to_datetime": to_datetime,
        "total_hours": total_hours,
        "reason": reason
    })

    # Clear conversation state (done!)
    clear_conversation_state(user_id, session_id or "legacy")

    # Format response
    if result.get("status") == "success":
        response = "✅ Regularization applied successfully!\n\n"
        response += f"📅 Date: {date}\n"
        response += f"🕐 Time: {from_time} to {to_time} ({hours}h {minutes}m)\n"
        response += f"📝 Reason: {reason}"
    else:
        response = RESPONSE_TEMPLATES["error_generic"].format(
            message=result.get('message', 'Failed to apply regularization')
        )

    return {
        "response": response,
        "sessionId": session_id
    }
