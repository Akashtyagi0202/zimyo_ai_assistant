"""
LangChain Tools for HRMS Operations
Foundation for AI Agents to autonomously perform HRMS tasks

This module defines HRMS operations as LangChain tools, enabling:
- AI agents to automatically call HRMS functions
- Function calling / tool use with LLMs
- Multi-step autonomous workflows
- Future: Complete HRMS/Payroll automation via AI

Usage:
    from langchain_tools import get_hrms_tools
    tools = get_hrms_tools(user_id="emp123")
    # Use with LangChain agents
"""

import logging
import asyncio
from typing import Dict, Any, List
from langchain.tools import Tool
from langchain.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)

# ===================== TOOL INPUT SCHEMAS =====================

class MarkAttendanceInput(BaseModel):
    """Input schema for mark_attendance tool"""
    location: str = Field(default="", description="Location where attendance is being marked (optional)")

class ApplyLeaveInput(BaseModel):
    """Input schema for apply_leave tool"""
    leave_type_name: str = Field(description="Type of leave (e.g., 'Casual Leave', 'Sick Leave')")
    from_date: str = Field(description="Start date in YYYY-MM-DD format")
    to_date: str = Field(description="End date in YYYY-MM-DD format")
    reasons: str = Field(description="Reason for taking leave")
    is_half_day: str = Field(default="0", description="1 for half day, 0 for full day")

class CheckLeaveBalanceInput(BaseModel):
    """Input schema for check_leave_balance tool"""
    pass  # No additional inputs needed, user_id is implicit

class GetLeaveTypesInput(BaseModel):
    """Input schema for get_leave_types tool"""
    pass  # No additional inputs needed, user_id is implicit

class ValidateLeaveRequestInput(BaseModel):
    """Input schema for validate_leave_request tool"""
    leave_type_name: str = Field(description="Type of leave to validate")
    from_date: str = Field(description="Start date in YYYY-MM-DD format")
    to_date: str = Field(description="End date in YYYY-MM-DD format")

# ===================== TOOL FUNCTIONS =====================

class HRMSToolkit:
    """
    Toolkit containing all HRMS operations as LangChain tools

    These tools can be used by LangChain agents to autonomously
    perform HRMS tasks based on user requests.
    """

    def __init__(self, user_id: str):
        """
        Initialize HRMS toolkit for a specific user

        Args:
            user_id: Employee ID for whom tools will operate
        """
        self.user_id = user_id
        self._mcp_client = None

    def _get_mcp_client(self):
        """Lazy load MCP client"""
        if self._mcp_client is None:
            from services.integration.mcp_client import get_http_mcp_client
            self._mcp_client = get_http_mcp_client()
        return self._mcp_client

    def _run_async(self, coroutine):
        """Helper to run async functions in sync context (for LangChain compatibility)"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)

    # ===================== TOOL IMPLEMENTATIONS =====================

    def mark_attendance(self, location: str = "") -> str:
        """
        Mark attendance for the employee

        Args:
            location: Location where attendance is being marked (optional)

        Returns:
            Success/failure message with attendance details
        """
        try:
            client = self._get_mcp_client()
            result = self._run_async(client.mark_attendance(self.user_id, location))

            if result.get("status") == "success":
                return f"✅ Attendance marked successfully at {location or 'default location'}"
            else:
                return f"❌ Failed to mark attendance: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in mark_attendance tool: {e}")
            return f"❌ Error marking attendance: {str(e)}"

    def apply_leave(
        self,
        leave_type_name: str,
        from_date: str,
        to_date: str,
        reasons: str,
        is_half_day: str = "0"
    ) -> str:
        """
        Apply for leave

        Args:
            leave_type_name: Type of leave (e.g., 'Casual Leave')
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            reasons: Reason for leave
            is_half_day: '1' for half day, '0' for full day

        Returns:
            Success/failure message with leave application details
        """
        try:
            client = self._get_mcp_client()
            result = self._run_async(client.apply_leave(
                user_id=self.user_id,
                leave_type_name=leave_type_name,
                from_date=from_date,
                to_date=to_date,
                reasons=reasons,
                is_half_day=is_half_day
            ))

            if result.get("status") == "success":
                return f"✅ Leave applied successfully: {leave_type_name} from {from_date} to {to_date}"
            else:
                return f"❌ Failed to apply leave: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in apply_leave tool: {e}")
            return f"❌ Error applying for leave: {str(e)}"

    def check_leave_balance(self) -> str:
        """
        Check current leave balance for the employee

        Returns:
            Leave balance details for all leave types
        """
        try:
            client = self._get_mcp_client()
            result = self._run_async(client.get_leave_balance(self.user_id))

            if result.get("status") == "success":
                balance_info = []
                for key, value in result.items():
                    if "_balance" in key and key != "status":
                        leave_type = key.replace("_balance", "").replace("_", " ").title()
                        balance_info.append(f"{leave_type}: {value} days")

                if balance_info:
                    return "📊 Your leave balance:\n" + "\n".join(balance_info)
                else:
                    return "📊 No leave balance information available"
            else:
                return f"❌ Failed to fetch leave balance: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in check_leave_balance tool: {e}")
            return f"❌ Error checking leave balance: {str(e)}"

    def get_leave_types(self) -> str:
        """
        Get available leave types for the employee's organization

        Returns:
            List of available leave types with their details
        """
        try:
            client = self._get_mcp_client()
            result = self._run_async(client.get_leave_types(self.user_id))

            if result.get("status") == "success":
                leave_types = result.get("leave_types", [])
                if leave_types:
                    types_info = []
                    for lt in leave_types:
                        name = lt.get("name", "Unknown")
                        balance = lt.get("balance", "N/A")
                        types_info.append(f"• {name} (Balance: {balance} days)")

                    return "📋 Available leave types:\n" + "\n".join(types_info)
                else:
                    return "📋 No leave types available"
            else:
                return f"❌ Failed to fetch leave types: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in get_leave_types tool: {e}")
            return f"❌ Error fetching leave types: {str(e)}"

    def validate_leave_request(
        self,
        leave_type_name: str,
        from_date: str,
        to_date: str
    ) -> str:
        """
        Validate if a leave request is allowed

        Args:
            leave_type_name: Type of leave to validate
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            Validation result with reasons if not allowed
        """
        try:
            client = self._get_mcp_client()
            result = self._run_async(client.validate_leave_request(
                user_id=self.user_id,
                leave_type_name=leave_type_name,
                from_date=from_date,
                to_date=to_date
            ))

            if result.get("is_valid"):
                return f"✅ Leave request is valid: {leave_type_name} from {from_date} to {to_date}"
            else:
                reasons = result.get("reasons", ["Unknown reason"])
                return f"❌ Leave request is NOT valid:\n" + "\n".join(f"• {r}" for r in reasons)

        except Exception as e:
            logger.error(f"Error in validate_leave_request tool: {e}")
            return f"❌ Error validating leave request: {str(e)}"

    # ===================== TOOL CREATION =====================

    def get_tools(self) -> List[Tool]:
        """
        Get all HRMS tools as LangChain Tool objects

        Returns:
            List of LangChain Tool objects ready for use with agents
        """
        return [
            Tool(
                name="mark_attendance",
                func=self.mark_attendance,
                description=(
                    "Mark attendance for the employee. "
                    "Use this when the employee wants to mark their attendance or check in. "
                    "Input: location (optional, where attendance is being marked)"
                ),
                args_schema=MarkAttendanceInput
            ),
            Tool(
                name="apply_leave",
                func=self.apply_leave,
                description=(
                    "Apply for leave on behalf of the employee. "
                    "Use this when the employee wants to apply for leave. "
                    "Requires: leave_type_name, from_date (YYYY-MM-DD), to_date (YYYY-MM-DD), "
                    "reasons, is_half_day (optional, '1' or '0')"
                ),
                args_schema=ApplyLeaveInput
            ),
            Tool(
                name="check_leave_balance",
                func=self.check_leave_balance,
                description=(
                    "Check the employee's current leave balance. "
                    "Use this when the employee wants to know their remaining leave days. "
                    "No inputs required."
                ),
                args_schema=CheckLeaveBalanceInput
            ),
            Tool(
                name="get_leave_types",
                func=self.get_leave_types,
                description=(
                    "Get list of available leave types for the employee's organization. "
                    "Use this when the employee asks what types of leaves are available. "
                    "No inputs required."
                ),
                args_schema=GetLeaveTypesInput
            ),
            Tool(
                name="validate_leave_request",
                func=self.validate_leave_request,
                description=(
                    "Validate if a leave request would be allowed before actually applying. "
                    "Use this to check if leave can be taken for specific dates. "
                    "Requires: leave_type_name, from_date (YYYY-MM-DD), to_date (YYYY-MM-DD)"
                ),
                args_schema=ValidateLeaveRequestInput
            )
        ]


# ===================== CONVENIENCE FUNCTION =====================

def get_hrms_tools(user_id: str) -> List[Tool]:
    """
    Convenience function to get HRMS tools for a specific user

    Usage:
        tools = get_hrms_tools("emp123")
        # Use with LangChain agent:
        from langchain.agents import initialize_agent
        agent = initialize_agent(tools, llm, agent="zero-shot-react-description")

    Args:
        user_id: Employee ID

    Returns:
        List of LangChain Tool objects
    """
    toolkit = HRMSToolkit(user_id)
    return toolkit.get_tools()
