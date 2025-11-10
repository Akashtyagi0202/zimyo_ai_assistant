"""
On-Duty Application Handler

Handles on-duty application flow with AI-guided conversation.
On-duty is used when employees work from different locations like WFH, client sites, etc.

Flow:
1. Check if all required fields are present
2. If complete → Apply on-duty via MCP
3. If incomplete → Ask for missing information

Required Fields:
- date: Date for on-duty (YYYY-MM-DD)
- from_time: Start time (HH:MM format)
- to_time: End time (HH:MM format)
- reason: Reason for on-duty (e.g., "WFH", "Client meeting")

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def handle_apply_onduty(
    user_id: str,
    extracted_data: Dict,
    ready_to_execute: bool,
    next_question: str,
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle on-duty application with AI-guided conversation.

    Process:
    1. Check if ready to execute (AI says all fields present)
    2. If not ready → Return next question to user
    3. If ready → Validate required fields
    4. Calculate total hours from time range
    5. Apply on-duty via MCP tool
    6. Return success/error message

    Args:
        user_id: Employee ID
        extracted_data: Data extracted by AI from user messages
        ready_to_execute: Whether AI says we have all required info
        next_question: Question to ask if not ready
        mcp_client: MCP client to call tools
        session_id: Conversation session ID

    Returns:
        {
            "response": "Message to user",
            "sessionId": "session_id"
        }

    Example Flow:
        User: "apply on duty"
        → Response: "किस तारीख के लिए? For which date?"

        User: "3 nov"
        → Response: "समय? Time range?"

        User: "9:30 AM to 6:30 PM"
        → Response: "कारण? Reason?"

        User: "WFH"
        → Response: "✅ On-duty applied successfully!"
    """
    from .shared import RESPONSE_TEMPLATES

    # STEP 1: Check if ready to execute
    if not ready_to_execute:
        logger.info(f"🔄 On-duty incomplete, asking: {next_question}")
        return {
            "response": next_question,
            "sessionId": session_id
        }

    # STEP 2: Validate required fields
    # Extract all required fields
    date = extracted_data.get("date")
    from_time = extracted_data.get("from_time")
    to_time = extracted_data.get("to_time")
    reason = extracted_data.get("reason")

    # Check for missing fields
    missing = []
    if not date:
        missing.append("date")
    if not from_time:
        missing.append("from_time")
    if not to_time:
        missing.append("to_time")
    if not reason:
        missing.append("reason")

    if missing:
        logger.warning(f"❌ Missing fields: {missing}")
        return {
            "response": f"कुछ जानकारी अधूरी है। Missing information: {', '.join(missing)}",
            "sessionId": session_id
        }

    # STEP 3: Format datetime strings
    # Combine date + time for Zimyo API format: "YYYY-MM-DD HH:mm:ss"
    try:
        from_datetime = f"{date} {from_time}:00"  # Add seconds
        to_datetime = f"{date} {to_time}:00"

        # Calculate total hours
        from_dt = datetime.strptime(from_datetime, "%Y-%m-%d %H:%M:%S")
        to_dt = datetime.strptime(to_datetime, "%Y-%m-%d %H:%M:%S")
        duration = to_dt - from_dt
        total_hours = f"{duration.seconds // 3600:02d}:{(duration.seconds % 3600) // 60:02d}:00"

        logger.info(f"📤 Applying on-duty: {date} {from_time}-{to_time} ({total_hours})")

    except ValueError as e:
        logger.error(f"❌ Date/time parsing error: {e}")
        return {
            "response": "तारीख या समय गलत है। Invalid date or time format.",
            "sessionId": session_id
        }

    # STEP 4: Apply on-duty via MCP
    try:
        result = await mcp_client.call_tool("apply_onduty", {
            "user_id": user_id,
            "from_datetime": from_datetime,
            "to_datetime": to_datetime,
            "total_hours": total_hours,
            "reason": reason
        })

        # MCP client already parses the response, so result is the actual data dict
        # Check if MCP client returned an error
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"❌ MCP error: {error_msg}")

            # Clear conversation state since request failed
            from services.operations.conversation_state import clear_conversation_state
            clear_conversation_state(user_id, session_id or "legacy")

            return {
                "response": f"❌ कुछ गड़बड़ हो गई। Something went wrong.\n\nError: {error_msg}",
                "sessionId": session_id
            }

        # Result is already the parsed data from MCP client
        result_data = result

        if result_data.get("status") == "success":
            # SUCCESS: Format success response
            logger.info("✅ On-duty applied successfully")

            # Clear conversation state since request is complete
            from services.operations.conversation_state import clear_conversation_state
            clear_conversation_state(user_id, session_id or "legacy")

            # Format date for display
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y")

            response = (
                "✅ ऑन-ड्यूटी सफलतापूर्वक लागू हो गई! On-duty applied successfully!\n\n"
                f"📅 तारीख। Date: {formatted_date}\n"
                f"⏰ समय। Time: {from_time} - {to_time}\n"
                f"⏱️ कुल घंटे। Total: {total_hours}\n"
                f"📝 कारण। Reason: {reason}"
            )

            return {
                "response": response,
                "sessionId": session_id
            }
        else:
            # ERROR from API
            error_msg = result_data.get("message", "Unknown error")
            logger.error(f"❌ On-duty application failed: {error_msg}")

            # Clear conversation state since request failed
            from services.operations.conversation_state import clear_conversation_state
            clear_conversation_state(user_id, session_id or "legacy")

            return {
                "response": f"❌ ऑन-ड्यूटी लागू नहीं हो सकी। On-duty application failed.\n\nकारण। Reason: {error_msg}",
                "sessionId": session_id
            }

    except Exception as e:
        logger.exception(f"❌ On-duty application exception: {e}")

        # Clear conversation state since request failed
        from services.operations.conversation_state import clear_conversation_state
        clear_conversation_state(user_id, session_id or "legacy")

        return {
            "response": f"❌ कुछ गड़बड़ हो गई। Something went wrong.\n\nError: {str(e)}",
            "sessionId": session_id
        }


# ============================================================================
# USAGE EXAMPLES (for developers)
# ============================================================================

"""
Example 1: Complete information in one message
----------------------------------------------
>>> result = await handle_apply_onduty(
...     user_id="240611",
...     extracted_data={
...         "date": "2025-11-03",
...         "from_time": "09:30",
...         "to_time": "18:30",
...         "reason": "WFH"
...     },
...     ready_to_execute=True,
...     next_question=None,
...     mcp_client=mcp_client,
...     session_id="sess123"
... )
>>> print(result['response'])
✅ ऑन-ड्यूटी सफलतापूर्वक लागू हो गई! On-duty applied successfully!
📅 तारीख। Date: 03 Nov 2025
⏰ समय। Time: 09:30 - 18:30
⏱️ कुल घंटे। Total: 09:00:00
📝 कारण। Reason: WFH


Example 2: Multi-message conversation
-------------------------------------
# Message 1
>>> result1 = await handle_apply_onduty(
...     "240611",
...     {"date": "2025-11-03"},
...     False,
...     "समय? Time range?",
...     mcp_client,
...     "sess123"
... )
>>> print(result1['response'])
समय? Time range?

# Message 2
>>> result2 = await handle_apply_onduty(
...     "240611",
...     {"date": "2025-11-03", "from_time": "09:30", "to_time": "18:30"},
...     False,
...     "कारण? Reason?",
...     mcp_client,
...     "sess123"
... )
>>> print(result2['response'])
कारण? Reason?

# Message 3
>>> result3 = await handle_apply_onduty(
...     "240611",
...     {"date": "2025-11-03", "from_time": "09:30", "to_time": "18:30", "reason": "WFH"},
...     True,
...     None,
...     mcp_client,
...     "sess123"
... )
>>> print(result3['response'])
✅ ऑन-ड्यूटी सफलतापूर्वक लागू हो गई! On-duty applied successfully!
"""
