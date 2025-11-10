"""
Attendance Handler

Handles attendance marking (check-in/check-out).
User asks: "punch in" or "check out from office"
Response: Marks attendance and confirms action with timestamp
"""

import logging
from typing import Dict, Any, Optional
from .shared import RESPONSE_TEMPLATES

logger = logging.getLogger(__name__)


async def handle_attendance(
    user_id: str,
    extracted_data: Dict,
    ready_to_execute: bool,
    next_question: str,
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle attendance marking (check-in/check-out).

    User said: "punch in" or "check out from office"
    Action: Marks attendance in system

    Example output:
        ✅ CHECK-IN marked successfully at 09:15 AM
        📍 Location: Office Building A

    Args:
        user_id: Employee ID
        extracted_data: Dictionary containing location if provided
        ready_to_execute: Whether all required info is present
        next_question: Question to ask if info incomplete
        mcp_client: MCP client instance
        session_id: Session ID for conversation tracking

    Returns:
        Response dictionary with attendance confirmation
    """
    from services.operations.conversation_state import clear_conversation_state

    if not ready_to_execute:
        logger.info(f"⏳ Attendance info incomplete, asking user")
        return {
            "response": next_question,
            "sessionId": session_id
        }

    # Ready to execute - mark attendance
    logger.info(f"✅ Marking attendance for user {user_id}")

    location = extracted_data.get("location", "")
    result = await mcp_client.call_tool("mark_attendance", {
        "user_id": user_id,
        "location": location
    })

    clear_conversation_state(user_id, session_id or "legacy")

    # Format response
    if result.get("status") == "success":
        response = RESPONSE_TEMPLATES["attendance_success"].format(
            action=result.get("action", "").upper(),
            time=result.get("time", "")
        )
        if location:
            response += RESPONSE_TEMPLATES["attendance_location"].format(location=location)
    else:
        response = RESPONSE_TEMPLATES["error_api"].format(
            resource="attendance",
            message=result.get('message', 'Failed to mark attendance')
        )

    return {
        "response": response,
        "sessionId": session_id
    }
