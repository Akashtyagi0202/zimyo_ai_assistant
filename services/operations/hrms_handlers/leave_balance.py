"""
Leave Balance Handler

Handles leave balance queries.
User asks: "what is my leave balance"
Response: Shows list of all leave types with remaining days
"""

import logging
from typing import Dict, Any, Optional
from .shared import RESPONSE_TEMPLATES

logger = logging.getLogger(__name__)


async def handle_leave_balance(
    user_id: str,
    mcp_client,
    session_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handle leave balance query.

    User asked: "what is my leave balance"
    Response: Shows list of all leave types with remaining days

    Example output:
        📊 Your current leave balance:
        • Sick Leave: 3.72 days
        • Casual Leave: 2.72 days
        • Earned Leave: 42 days

    Args:
        user_id: Employee ID
        mcp_client: MCP client instance
        session_id: Session ID for conversation tracking

    Returns:
        Response dictionary with leave balance information
    """
    logger.info(f"💼 Fetching leave balance for user {user_id}")

    # Get leave types first (for validation)
    policy_result = await mcp_client.call_tool("get_leave_types", {
        "user_id": user_id
    })

    if policy_result.get("status") != "success":
        return {
            "response": RESPONSE_TEMPLATES["error_api"].format(
                resource="leave information",
                message=policy_result.get('message', 'Unknown error')
            ),
            "sessionId": session_id
        }

    # Get actual balance
    balance_result = await mcp_client.call_tool("get_leave_balance", {
        "user_id": user_id
    })

    if balance_result.get("status") != "success":
        return {
            "response": RESPONSE_TEMPLATES["error_api"].format(
                resource="leave balance",
                message=balance_result.get('message', 'Unknown error')
            ),
            "sessionId": session_id
        }

    # Format response
    leave_balance = balance_result.get("leave_balance", {})

    if not leave_balance:
        return {
            "response": RESPONSE_TEMPLATES["balance_empty"],
            "sessionId": session_id
        }

    # Build formatted list using template
    balance_lines = [
        RESPONSE_TEMPLATES["balance_item"].format(leave_type=lt, days=d)
        for lt, d in leave_balance.items()
    ]

    response = RESPONSE_TEMPLATES["balance_header"] + "\n".join(balance_lines)

    return {
        "response": response,
        "sessionId": session_id
    }
