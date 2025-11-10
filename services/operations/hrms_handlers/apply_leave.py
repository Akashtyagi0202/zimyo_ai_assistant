"""
Apply Leave Handler

Handles leave application requests.
User asks: "apply sick leave from 4 nov to 6 nov for health issues"
Response: Validates, applies leave, and confirms with details
"""

import logging
from typing import Dict, Any, Optional
from .shared import RESPONSE_TEMPLATES

logger = logging.getLogger(__name__)


async def handle_apply_leave(
    user_id: str,
    extracted_data: Dict,
    ready_to_execute: bool,
    next_question: str,
    available_leave_types: list,  # Kept for future use
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle leave application.

    User wants to apply for leave. May take multiple messages to collect:
    - Leave type (Sick, Casual, Earned, etc.)
    - Start date
    - End date
    - Reason

    Example conversation:
        User: "apply leave"
        Bot: "किस प्रकार की छुट्टी? What type?"

        User: "sick"
        Bot: "कब से? Start date?"

        User: "4 nov"
        Bot: "कारण? Reason?"

        User: "health issues"
        Bot: "✅ Leave applied successfully!"

    Example output:
        ✅ छुट्टी सफलतापूर्वक लागू हो गई! Leave applied successfully!

        📋 Type: Sick Leave
        📅 Dates: 2025-11-04 to 2025-11-06 (3 days)
        📝 Reason: health issues

    Args:
        user_id: Employee ID
        extracted_data: Dictionary with leave_type, from_date, to_date, reason
        ready_to_execute: Whether all required info is present
        next_question: Question to ask if info incomplete
        available_leave_types: List of valid leave types (reserved for future use)
        mcp_client: MCP client instance
        session_id: Session ID for conversation tracking

    Returns:
        Response dictionary with leave application result
    """
    from services.operations.conversation_state import clear_conversation_state

    # If not ready, ask question (state already saved in handle_hrms_with_ai)
    if not ready_to_execute:
        logger.info(f"⏳ Leave info incomplete, asking user")
        return {
            "response": next_question,
            "sessionId": session_id
        }

    # Ready to execute - first validate
    logger.info(f"🔍 Validating leave request for user {user_id}")

    validation_result = await mcp_client.call_tool("validate_leave_request", {
        "user_id": user_id,
        "leave_type_name": extracted_data["leave_type"],
        "from_date": extracted_data["from_date"],
        "to_date": extracted_data["to_date"]
    })

    # Validation failed - show errors (context already saved)
    if not validation_result.get("is_valid", False):
        errors = validation_result.get("errors", [])
        logger.warning(f"❌ Validation failed: {errors}")

        return {
            "response": RESPONSE_TEMPLATES["error_generic"].format(
                message='; '.join(errors)
            ),
            "sessionId": session_id
        }

    # Validation passed - apply leave
    logger.info(f"✅ Applying leave for user {user_id}")

    apply_result = await mcp_client.call_tool("apply_leave", {
        "user_id": user_id,
        "leave_type_name": extracted_data["leave_type"],
        "from_date": extracted_data["from_date"],
        "to_date": extracted_data["to_date"],
        "reasons": extracted_data.get("reason", f"{extracted_data['leave_type']} application")
    })

    # Clear conversation state (done!)
    clear_conversation_state(user_id, session_id or "legacy")

    # Format success/error response using templates
    if apply_result.get("status") == "success":
        days = apply_result.get("days_requested", 1)
        response = RESPONSE_TEMPLATES["leave_success"]
        response += RESPONSE_TEMPLATES["leave_type"].format(leave_type=extracted_data['leave_type'])
        response += RESPONSE_TEMPLATES["leave_dates"].format(
            from_date=extracted_data['from_date'],
            to_date=extracted_data['to_date'],
            days=days
        )
        response += RESPONSE_TEMPLATES["leave_reason"].format(
            reason=extracted_data.get('reason', 'Not specified')
        )
    else:
        response = RESPONSE_TEMPLATES["error_generic"].format(
            message=apply_result.get('message', 'Failed to apply leave')
        )

    return {
        "response": response,
        "sessionId": session_id
    }
