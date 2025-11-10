"""
Salary Slip Handler

Handles salary slip download queries.
Shows salary breakdown and provides PDF download link for employees.

Flow:
1. User asks for salary slip (optionally for specific month/year)
2. AI extracts month/year from query or defaults to current month
3. Fetch salary slip via MCP
4. Format and display salary details with download link

This is a simple read-only query with no complex flow.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64

logger = logging.getLogger(__name__)


async def handle_get_salary_slip(
    user_id: str,
    mcp_client,
    session_id: Optional[str],
    ai_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle salary slip download query.

    Simple operation - fetch and display salary slip with download link.

    Process:
    1. Extract month/year from AI response (defaults to current month)
    2. Call MCP to get salary slip
    3. Parse and format the response
    4. Return formatted salary details with download link

    Args:
        user_id: Employee ID
        mcp_client: MCP client to call tools
        session_id: Conversation session ID
        ai_response: AI extracted values (month, year)

    Returns:
        {
            "response": "Formatted salary slip details with download link",
            "sessionId": "session_id"
        }

    Example:
        User: "salary slip for October 2025"
        → Response:
        "💰 वेतन पर्ची। Salary Slip - October 2025

        📊 विवरण। Details:
        • सकल वेतन। Gross Salary: ₹50,000
        • शुद्ध वेतन। Net Salary: ₹45,000
        • कटौती। Deductions: ₹5,000
        • CTC: ₹6,00,000

        📥 डाउनलोड करें। Download: [Click here](salary_slip_link)"
    """
    try:
        # STEP 1: Get month and year
        current_date = datetime.now()

        # Extract from AI response or default to current month
        if ai_response and ai_response.get("values"):
            values = ai_response["values"]
            month = values.get("month", current_date.month)
            year = values.get("year", current_date.year)
        else:
            # Default to current month/year
            month = current_date.month
            year = current_date.year

        logger.info(f"📤 Fetching salary slip for user: {user_id}, Month: {month}, Year: {year}")

        # STEP 2: Get salary slip from MCP
        result = await mcp_client.call_tool("get_salary_slip", {
            "user_id": user_id,
            "month": month,
            "year": year
        })

        # STEP 3: Parse MCP response
        # MCP client already parses the response, so result is the actual data dict
        import json

        # Check if result is a string (error case) or dict
        if isinstance(result, str):
            logger.error(f"❌ MCP returned string error: {result}")
            return {
                "response": f"❌ वेतन पर्ची नहीं मिल सकी। Could not fetch salary slip.\\n\\nError: {result}",
                "sessionId": session_id
            }

        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"❌ MCP error: {error_msg}")
            return {
                "response": f"❌ वेतन पर्ची नहीं मिल सकी। Could not fetch salary slip.\\n\\nError: {error_msg}",
                "sessionId": session_id
            }

        result_data = result

        if result_data.get("status") == "success":
            salary_details = result_data.get("salary_details", {})
            salary_slip_buffer = result_data.get("salary_slip_buffer", "")

            # STEP 4: Format salary slip details
            logger.info(f"✅ Salary slip fetched successfully")
            logger.debug(f"📦 API Response keys: {list(result_data.keys())}")
            logger.debug(f"📦 Salary slip buffer present: {bool(salary_slip_buffer)}")
            logger.debug(f"📦 Salary slip buffer length: {len(salary_slip_buffer) if salary_slip_buffer else 0}")

            # Get month name
            month_name = salary_details.get("month_name", "")
            if not month_name:
                month_names = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ]
                month_name = month_names[month - 1] if 1 <= month <= 12 else str(month)

            response_lines = [f"💰 वेतन पर्ची। Salary Slip - {month_name} {year}\\n"]

            # Add salary details
            response_lines.append("📊 विवरण। Details:")

            gross_salary = salary_details.get("gross_salary", 0)
            net_salary = salary_details.get("net_salary", 0)
            deductions = salary_details.get("deductions", 0)
            ctc = salary_details.get("ctc", 0)

            # Format amounts with Indian numbering system
            response_lines.append(f"• सकल वेतन। Gross Salary: ₹{gross_salary:,.2f}")
            response_lines.append(f"• शुद्ध वेतन। Net Salary: ₹{net_salary:,.2f}")
            response_lines.append(f"• कटौती। Deductions: ₹{deductions:,.2f}")
            response_lines.append(f"• CTC: ₹{ctc:,.2f}")

            # Add head-wise breakdown if available
            head_details = salary_details.get("head_details", [])
            if head_details and len(head_details) > 0:
                response_lines.append("\\n💼 विवरण। Breakdown:")

                for head in head_details[:10]:  # Show max 10 items
                    head_name = head.get("head_name", "")
                    amount = head.get("amount", 0)

                    if head_name and amount:
                        response_lines.append(f"  • {head_name}: ₹{amount:,.2f}")

            # Add download link
            if salary_slip_buffer:
                # Create a data URL for the PDF
                response_lines.append(f"\\n📥 डाउनलोड करें। Download:")
                response_lines.append(f"PDF available for download (base64 encoded)")
                response_lines.append(f"\\n[Note: PDF buffer available. Implement download mechanism in frontend.]")
            else:
                response_lines.append(f"\\n⚠️ PDF डाउनलोड उपलब्ध नहीं है। PDF download not available.")

            # Join all lines
            response = "\\n".join(response_lines)

            return {
                "response": response,
                "sessionId": session_id,
                "salary_slip_buffer": salary_slip_buffer  # Include buffer for frontend to download
            }

        else:
            # Error from API
            error_msg = result_data.get("message", "Unknown error")
            logger.error(f"❌ Salary slip fetch failed: {error_msg}")

            return {
                "response": f"❌ वेतन पर्ची नहीं मिल सकी। Could not fetch salary slip.\\n\\nकारण। Reason: {error_msg}",
                "sessionId": session_id
            }

    except Exception as e:
        logger.exception(f"❌ Salary slip fetch exception: {e}")
        return {
            "response": f"❌ कुछ गड़बड़ हो गई। Something went wrong.\\n\\nError: {str(e)}",
            "sessionId": session_id
        }


# ============================================================================
# USAGE EXAMPLES (for developers)
# ============================================================================

"""
Example 1: User asks for current month salary slip
-------------------------------------------------
>>> result = await handle_get_salary_slip(
...     user_id="240611",
...     mcp_client=mcp_client,
...     session_id="sess123"
... )
>>> print(result['response'])
💰 वेतन पर्ची। Salary Slip - November 2025

📊 विवरण। Details:
• सकल वेतन। Gross Salary: ₹50,000.00
• शुद्ध वेतन। Net Salary: ₹45,000.00
• कटौती। Deductions: ₹5,000.00
• CTC: ₹6,00,000.00

💼 विवरण। Breakdown:
  • Basic Salary: ₹30,000.00
  • HRA: ₹10,000.00
  • PF: ₹2,000.00

📥 डाउनलोड करें। Download:
PDF available for download (base64 encoded)


Example 2: User asks for specific month
----------------------------------------
>>> result = await handle_get_salary_slip(
...     user_id="240611",
...     mcp_client=mcp_client,
...     session_id="sess123",
...     ai_response={"values": {"month": 10, "year": 2025}}
... )
>>> print(result['response'])
💰 वेतन पर्ची। Salary Slip - October 2025
...
"""
