"""
Execution Node for LangGraph

Executes HRMS actions (leave application, regularization, etc.)

Author: Zimyo AI Team
"""

import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


def execute_action_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the HRMS action.

    Args:
        state: Current workflow state

    Returns:
        Updated state with execution result
    """
    logger.info(f"⚡ Execution Node - Intent: {state.get('intent')}")

    intent = state.get("intent", "")
    user_id = state.get("user_id")
    extracted_data = state.get("extracted_data", {})

    # Route to appropriate handler
    try:
        if intent == "apply_leave":
            result = _execute_leave_application(user_id, extracted_data)

        elif intent == "apply_regularization":
            result = _execute_regularization(user_id, extracted_data)

        elif intent == "apply_onduty":
            result = _execute_onduty(user_id, extracted_data)

        elif intent == "check_leave_balance":
            result = _execute_balance_query(user_id)

        elif intent == "mark_attendance":
            result = _execute_attendance(user_id, extracted_data)

        elif intent == "get_holidays":
            result = _execute_holidays(user_id)

        elif intent == "get_salary_slip":
            result = _execute_salary_slip(user_id, extracted_data)

        else:
            result = {"success": False, "message": "Unknown intent", "data": {}}

        logger.info(f"✅ Execution result: success={result.get('success', False)}")

        return {
            **state,
            "execution_result": result,
            "current_step": "executed"
        }

    except Exception as e:
        logger.error(f"❌ Execution failed: {e}")
        return {
            **state,
            "execution_result": {"success": False, "message": str(e), "data": {}},
            "current_step": "execution_failed"
        }


def _execute_leave_application(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute leave application."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.apply_leave import handle_apply_leave

        mcp_client = get_http_mcp_client()

        # Run async handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_apply_leave(
                user_id=user_id,
                extracted_data=data,
                ready=True,
                next_question=None,
                available_leave_types=[],
                mcp_client=mcp_client,
                session_id=None
            )
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Leave application failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_regularization(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute attendance regularization."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.apply_regularization import handle_apply_regularization

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_apply_regularization(
                user_id=user_id,
                extracted_data=data,
                ready=True,
                next_question=None,
                mcp_client=mcp_client,
                session_id=None
            )
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Regularization failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_onduty(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute on-duty application."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.apply_onduty import handle_apply_onduty

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_apply_onduty(
                user_id=user_id,
                extracted_data=data,
                ready=True,
                next_question=None,
                mcp_client=mcp_client,
                session_id=None
            )
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ On-duty application failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_balance_query(user_id: str) -> Dict[str, Any]:
    """Execute leave balance query."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.leave_balance import handle_leave_balance

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_leave_balance(user_id, mcp_client, None)
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Balance query failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_attendance(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute attendance marking."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.attendance import handle_attendance

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_attendance(
                user_id=user_id,
                extracted_data=data,
                ready=True,
                next_question=None,
                mcp_client=mcp_client,
                session_id=None
            )
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Attendance marking failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_holidays(user_id: str) -> Dict[str, Any]:
    """Execute holiday query."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.get_holidays import handle_get_holidays

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_get_holidays(user_id, mcp_client, None)
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Holiday query failed: {e}")
        return {"success": False, "message": str(e), "data": {}}


def _execute_salary_slip(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute salary slip query."""
    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.get_salary_slip import handle_get_salary_slip

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            handle_get_salary_slip(user_id, mcp_client, None, {"values": data})
        )
        loop.close()

        return {"success": True, "message": result.get("response", ""), "data": result}

    except Exception as e:
        logger.error(f"❌ Salary slip query failed: {e}")
        return {"success": False, "message": str(e), "data": {}}
