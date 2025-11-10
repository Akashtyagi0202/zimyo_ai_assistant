"""
Holidays Information Handler

Handles holiday information queries.
Shows upcoming company holidays to help employees plan their leaves better.

Flow:
1. User asks for holidays
2. Fetch upcoming holidays via MCP
3. Format and display in readable format

This is a simple read-only query with no complex flow.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def handle_get_holidays(
    user_id: str,
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle upcoming holidays query.

    Simple read-only operation - no conversation flow needed.
    Just fetch and display holidays.

    Process:
    1. Call MCP to get upcoming holidays
    2. Parse and format the response
    3. Return formatted holiday list to user

    Args:
        user_id: Employee ID
        mcp_client: MCP client to call tools
        session_id: Conversation session ID

    Returns:
        {
            "response": "Formatted holiday list",
            "sessionId": "session_id"
        }

    Example:
        User: "upcoming holidays"
        → Response:
        "🎉 आगामी छुट्टियां। Upcoming Holidays:

        📅 12 Nov 2025 (Wed) - Diwali
        📅 25 Dec 2025 (Thu) - Christmas
        📅 26 Jan 2026 (Mon) - Republic Day"
    """
    try:
        logger.info(f"📤 Fetching holidays for user: {user_id}")

        # STEP 1: Get holidays from MCP
        result = await mcp_client.call_tool("get_upcoming_holidays", {
            "user_id": user_id
        })

        # STEP 2: Parse MCP response
        # MCP client already parses the response, so result is the actual data dict
        import json

        # Check if result is a string (error case) or dict
        if isinstance(result, str):
            logger.error(f"❌ MCP returned string error: {result}")
            return {
                "response": f"❌ छुट्टियों की जानकारी नहीं मिल सकी। Could not fetch holidays.\n\nError: {result}",
                "sessionId": session_id
            }

        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"❌ MCP error: {error_msg}")
            return {
                "response": f"❌ छुट्टियों की जानकारी नहीं मिल सकी। Could not fetch holidays.\n\nError: {error_msg}",
                "sessionId": session_id
            }

        result_data = result

        if result_data.get("status") == "success":
            holidays = result_data.get("holidays", [])

            if not holidays or len(holidays) == 0:
                # No upcoming holidays
                logger.info("ℹ️ No upcoming holidays found")
                return {
                    "response": "📅 फिलहाल कोई आगामी छुट्टियां नहीं हैं। No upcoming holidays at the moment.",
                    "sessionId": session_id
                }

            # STEP 3: Format holidays list
            logger.info(f"✅ Found {len(holidays)} upcoming holidays")

            response_lines = ["🎉 आगामी छुट्टियां। Upcoming Holidays:\n"]

            for holiday in holidays[:10]:  # Show max 10 holidays
                # Extract holiday data
                # API returns uppercase field names
                name = holiday.get("NAME", "Holiday")
                date_str = holiday.get("HOLIDAY_DATE", "")
                holiday_type = holiday.get("HOLIDAY_TYPE_NAME", "")

                # Format date for display
                try:
                    if date_str:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        formatted_date = date_obj.strftime("%d %b %Y")
                        day_short = date_obj.strftime("%a")  # Mon, Tue, etc.

                        # Format: 📅 12 Nov 2025 (Wed) - Diwali
                        response_lines.append(f"📅 {formatted_date} ({day_short}) - {name}")
                    else:
                        response_lines.append(f"📅 {name}")
                except Exception as e:
                    logger.warning(f"Date parsing error: {e}")
                    response_lines.append(f"📅 {name}")

            # Join all lines
            response = "\n".join(response_lines)

            return {
                "response": response,
                "sessionId": session_id
            }

        else:
            # Error from API
            error_msg = result_data.get("message", "Unknown error")
            logger.error(f"❌ Holiday fetch failed: {error_msg}")

            return {
                "response": f"❌ छुट्टियों की जानकारी नहीं मिल सकी। Could not fetch holiday information.\n\nकारण। Reason: {error_msg}",
                "sessionId": session_id
            }

    except Exception as e:
        logger.exception(f"❌ Holiday fetch exception: {e}")
        return {
            "response": f"❌ कुछ गड़बड़ हो गई। Something went wrong.\n\nError: {str(e)}",
            "sessionId": session_id
        }


# ============================================================================
# USAGE EXAMPLES (for developers)
# ============================================================================

"""
Example: User asks for upcoming holidays
-----------------------------------------
>>> result = await handle_get_holidays(
...     user_id="240611",
...     mcp_client=mcp_client,
...     session_id="sess123"
... )
>>> print(result['response'])
🎉 आगामी छुट्टियां। Upcoming Holidays:

📅 12 Nov 2025 (Wed) - Diwali
📅 25 Dec 2025 (Thu) - Christmas
📅 26 Jan 2026 (Mon) - Republic Day
📅 15 Aug 2026 (Sat) - Independence Day
"""
