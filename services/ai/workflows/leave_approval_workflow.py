"""
Advanced Leave Approval Workflow with LangGraph

This workflow demonstrates the power of LangGraph for complex HRMS processes:
- Multi-step approval chain
- Conditional routing based on leave balance and duration
- Manager approval simulation
- Alternative leave type suggestions
- State persistence across messages

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

# LangGraph imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# Local imports
from services.ai.langgraph_config import LeaveApplicationState, get_checkpointer
from services.ai.workflows.intent_extraction import extract_intent_node

logger = logging.getLogger(__name__)


# ============================================================================
# WORKFLOW NODES
# ============================================================================

def check_leave_balance_node(state: LeaveApplicationState) -> LeaveApplicationState:
    """
    Check if user has sufficient leave balance.

    Args:
        state: Current workflow state

    Returns:
        Updated state with balance info
    """
    logger.info(f"💰 Checking leave balance for user {state['user_id']}")

    try:
        from services.integration.mcp_client import get_http_mcp_client
        import asyncio

        mcp_client = get_http_mcp_client()
        user_id = state["user_id"]

        # Fetch leave balance
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Get balance from MCP (simplified - you'd call actual MCP method)
        # For now, using dummy data
        leave_balance = 5.0  # Dummy balance

        loop.close()

        # Calculate required days
        from_date = datetime.strptime(state["extracted_data"].get("from_date", ""), "%Y-%m-%d")
        to_date = datetime.strptime(state["extracted_data"].get("to_date", state["extracted_data"].get("from_date", "")), "%Y-%m-%d")
        required_days = (to_date - from_date).days + 1

        has_sufficient = leave_balance >= required_days

        logger.info(f"📊 Balance: {leave_balance}, Required: {required_days}, Sufficient: {has_sufficient}")

        return {
            **state,
            "leave_balance": leave_balance,
            "has_sufficient_balance": has_sufficient,
            "current_step": "balance_checked"
        }

    except Exception as e:
        logger.error(f"❌ Balance check failed: {e}")
        return {
            **state,
            "leave_balance": 0.0,
            "has_sufficient_balance": False,
            "current_step": "balance_check_failed"
        }


def suggest_alternatives_node(state: LeaveApplicationState) -> LeaveApplicationState:
    """
    Suggest alternative leave types when balance is insufficient.

    Args:
        state: Current workflow state

    Returns:
        Updated state with suggestions
    """
    logger.info("💡 Generating alternative leave suggestions")

    current_type = state["extracted_data"].get("leave_type", "")
    suggestions = []

    # Suggest alternative leave types
    if "Sick" in current_type:
        suggestions = [
            "🏥 Casual Leave - If this is not a medical emergency",
            "📅 Unpaid Leave - If you've exhausted paid leaves",
            "🏠 Work From Home - Consider WFH instead of taking leave"
        ]
    elif "Casual" in current_type:
        suggestions = [
            "🏥 Sick Leave - If you're not feeling well",
            "📅 Earned Leave - If eligible",
            "🏠 Work From Home - Consider WFH for partial days"
        ]
    else:
        suggestions = [
            "🏥 Check Sick Leave balance",
            "📅 Check Casual Leave balance",
            "💬 Contact HR for more options"
        ]

    response = f"""⚠️ Insufficient {current_type} balance!

Current balance: {state.get('leave_balance', 0)} days

**Alternative options:**
{chr(10).join(suggestions)}

Would you like to try a different leave type?"""

    return {
        **state,
        "alternative_suggestions": suggestions,
        "response": response,
        "current_step": "alternatives_suggested"
    }


def apply_leave_node(state: LeaveApplicationState) -> LeaveApplicationState:
    """
    Apply for leave (calls actual HRMS system).

    Args:
        state: Current workflow state

    Returns:
        Updated state with application result
    """
    logger.info(f"📝 Applying leave for user {state['user_id']}")

    try:
        from services.integration.mcp_client import get_http_mcp_client
        from services.operations.hrms_handlers.apply_leave import handle_apply_leave
        import asyncio

        mcp_client = get_http_mcp_client()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            handle_apply_leave(
                user_id=state["user_id"],
                extracted_data=state["extracted_data"],
                ready=True,
                next_question=None,
                available_leave_types=[],
                mcp_client=mcp_client,
                session_id=state.get("session_id")
            )
        )

        loop.close()

        logger.info("✅ Leave applied successfully")

        return {
            **state,
            "response": result.get("response", "✅ Leave applied!"),
            "ready_to_execute": True,
            "current_step": "leave_applied"
        }

    except Exception as e:
        logger.error(f"❌ Leave application failed: {e}")
        return {
            **state,
            "response": f"❌ Failed to apply leave: {str(e)}",
            "ready_to_execute": False,
            "current_step": "application_failed"
        }


def manager_approval_node(state: LeaveApplicationState) -> LeaveApplicationState:
    """
    Simulate manager approval step.

    In production, this would:
    - Send notification to manager
    - Wait for approval (human-in-the-loop)
    - Update state when manager responds

    Args:
        state: Current workflow state

    Returns:
        Updated state with approval status
    """
    logger.info("👔 Manager approval step")

    # In real system, this would trigger notification and wait
    # For now, we'll simulate approval based on rules

    from_date = state["extracted_data"].get("from_date", "")
    to_date = state["extracted_data"].get("to_date", from_date)

    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        duration = (to_dt - from_dt).days + 1

        # Auto-approve if <= 5 days, otherwise require manual approval
        if duration <= 5:
            approval_status = "approved"
            response = f"""✅ Leave request automatically approved!

📋 Leave Details:
• Type: {state["extracted_data"].get("leave_type")}
• Duration: {duration} day(s)
• Dates: {from_date} to {to_date}
• Reason: {state["extracted_data"].get("reason")}

Your leave has been recorded in the system."""

        else:
            approval_status = "pending_manager"
            response = f"""⏳ Leave request sent to manager for approval

📋 Request Details:
• Type: {state["extracted_data"].get("leave_type")}
• Duration: {duration} day(s)
• Dates: {from_date} to {to_date}

You'll be notified once your manager reviews the request."""

        return {
            **state,
            "approval_status": approval_status,
            "response": response,
            "current_step": "approval_processed"
        }

    except Exception as e:
        logger.error(f"❌ Approval check failed: {e}")
        return {
            **state,
            "approval_status": "error",
            "response": f"❌ Error processing approval: {str(e)}",
            "current_step": "approval_failed"
        }


def ask_for_info_node(state: LeaveApplicationState) -> LeaveApplicationState:
    """
    Ask user for missing information.

    Args:
        state: Current workflow state

    Returns:
        Updated state with question
    """
    logger.info("❓ Asking for more information")

    extracted_data = state.get("extracted_data", {})

    # Determine what's missing
    if not extracted_data.get("leave_type"):
        question = "किस प्रकार की छुट्टी चाहिए? What type of leave? (Sick, Casual, Earned)"
    elif not extracted_data.get("from_date"):
        question = "किस तारीख से छुट्टी चाहिए? From which date?"
    elif not extracted_data.get("reason"):
        question = "छुट्टी का कारण बताएं? What's the reason for leave?"
    else:
        question = "कृपया अधिक जानकारी दें। Please provide more details."

    return {
        **state,
        "response": question,
        "current_step": "awaiting_user_input"
    }


# ============================================================================
# CONDITIONAL ROUTING
# ============================================================================

def check_if_complete(state: LeaveApplicationState) -> str:
    """Check if we have all required information."""
    data = state.get("extracted_data", {})

    if data.get("leave_type") and data.get("from_date") and data.get("reason"):
        return "complete"
    return "incomplete"


def check_balance_sufficient(state: LeaveApplicationState) -> str:
    """Check if leave balance is sufficient."""
    if state.get("has_sufficient_balance", False):
        return "sufficient"
    return "insufficient"


def check_approval_needed(state: LeaveApplicationState) -> str:
    """Check if manager approval is needed."""
    if state.get("requires_approval", False):
        return "needs_approval"
    return "auto_approve"


# ============================================================================
# WORKFLOW BUILDER
# ============================================================================

def build_leave_approval_workflow() -> StateGraph:
    """
    Build advanced leave approval workflow with LangGraph.

    Workflow:
    1. Extract intent and data
    2. Check if complete → If not, ask user
    3. Check leave balance → If insufficient, suggest alternatives
    4. Check if needs approval → Route accordingly
    5. Apply leave or send for approval
    6. Generate response

    Returns:
        Compiled StateGraph
    """
    logger.info("🏗️ Building leave approval workflow")

    # Create graph
    graph = StateGraph(LeaveApplicationState)

    # Add nodes
    graph.add_node("extract_intent", extract_intent_node)
    graph.add_node("ask_for_info", ask_for_info_node)
    graph.add_node("check_balance", check_leave_balance_node)
    graph.add_node("suggest_alternatives", suggest_alternatives_node)
    graph.add_node("manager_approval", manager_approval_node)
    graph.add_node("apply_leave", apply_leave_node)

    # Set entry point
    graph.set_entry_point("extract_intent")

    # Conditional: Check if we have all info
    graph.add_conditional_edges(
        "extract_intent",
        check_if_complete,
        {
            "complete": "check_balance",
            "incomplete": "ask_for_info"
        }
    )

    graph.add_edge("ask_for_info", END)

    # Conditional: Check balance
    graph.add_conditional_edges(
        "check_balance",
        check_balance_sufficient,
        {
            "sufficient": "manager_approval",
            "insufficient": "suggest_alternatives"
        }
    )

    graph.add_edge("suggest_alternatives", END)

    # Conditional: Check if needs approval
    graph.add_conditional_edges(
        "manager_approval",
        check_approval_needed,
        {
            "needs_approval": END,  # Wait for manager
            "auto_approve": "apply_leave"
        }
    )

    graph.add_edge("apply_leave", END)

    # Compile with checkpointer
    checkpointer = get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("✅ Leave approval workflow compiled")
    return compiled


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['build_leave_approval_workflow']


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
Example: Run leave approval workflow
-------------------------------------
from services.ai.workflows.leave_approval_workflow import build_leave_approval_workflow
from services.ai.langgraph_config import create_workflow_config

# Build workflow
workflow = build_leave_approval_workflow()

# Initial state
initial_state = {
    "user_id": "240611",
    "session_id": "sess123",
    "user_message": "apply sick leave for tomorrow",
    "messages": [],
    "intent": "",
    "extracted_data": {},
    "current_step": "start",
    "next_action": "",
    "is_valid": False,
    "validation_errors": [],
    "requires_approval": False,
    "approval_status": "pending",
    "approver_id": None,
    "response": "",
    "ready_to_execute": False,
    "leave_type": None,
    "from_date": None,
    "to_date": None,
    "reason": None,
    "leave_balance": None,
    "has_sufficient_balance": False,
    "alternative_suggestions": []
}

# Run workflow
config = create_workflow_config("240611", "sess123")
result = workflow.invoke(initial_state, config)

print(result["response"])

# Stream steps (see each node execution)
for step in workflow.stream(initial_state, config):
    print(f"Step: {step}")
"""
