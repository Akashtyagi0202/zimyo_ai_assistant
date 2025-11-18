"""
LangGraph Configuration for HRMS AI Assistant

This module provides LangGraph setup for complex HRMS workflows:
- State management with Redis checkpointing
- Workflow orchestration
- Conditional routing
- Multi-agent coordination
- Human-in-the-loop approvals

Author: Zimyo AI Team
"""

import os
import logging
from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional
from operator import add

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Redis checkpointing (for production)
try:
    from langgraph_checkpoint import RedisSaver
    REDIS_CHECKPOINT_AVAILABLE = True
except ImportError:
    REDIS_CHECKPOINT_AVAILABLE = False
    logging.warning("Redis checkpointing not available, using MemorySaver")

# Local imports
from config import REDIS_HOST, REDIS_PORT, REDIS_DB
# Use existing working LLM config (no dependency conflicts)
# from services.ai.langchain_config import get_llm

logger = logging.getLogger(__name__)


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class HRMSState(TypedDict):
    """
    Base state for all HRMS workflows.

    This state is passed through all nodes in the graph.
    Each node can read and modify the state.
    """
    # User context
    user_id: str
    session_id: str

    # Conversation
    messages: Annotated[Sequence[BaseMessage], add]
    user_message: str

    # Intent and extracted data
    intent: str
    extracted_data: Dict[str, Any]

    # Workflow control
    current_step: str
    next_action: str

    # Data validation
    is_valid: bool
    validation_errors: list

    # Approval workflow
    requires_approval: bool
    approval_status: str  # pending, approved, rejected
    approver_id: Optional[str]

    # Response
    response: str
    ready_to_execute: bool


class LeaveApplicationState(HRMSState):
    """State for leave application workflow."""
    leave_type: Optional[str]
    from_date: Optional[str]
    to_date: Optional[str]
    reason: Optional[str]
    leave_balance: Optional[float]
    has_sufficient_balance: bool
    alternative_suggestions: list


class RegularizationState(HRMSState):
    """State for attendance regularization workflow."""
    date: Optional[str]
    from_time: Optional[str]
    to_time: Optional[str]
    reason: Optional[str]
    attendance_record: Optional[Dict]
    auto_approvable: bool
    requires_manager_approval: bool


class OnDutyState(HRMSState):
    """State for on-duty application workflow."""
    date: Optional[str]
    from_time: Optional[str]
    to_time: Optional[str]
    reason: Optional[str]
    on_duty_type: Optional[str]  # WFH, Client Visit, Field Work
    requires_manager_approval: bool


# ============================================================================
# CHECKPOINTER SETUP
# ============================================================================

def get_checkpointer():
    """
    Get LangGraph checkpointer for state persistence.

    Returns:
        MemorySaver (development) or RedisSaver (production)
    """
    # In production, use Redis for persistence
    if REDIS_CHECKPOINT_AVAILABLE and os.getenv("USE_REDIS_CHECKPOINT", "false").lower() == "true":
        redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        logger.info(f"🔄 Using Redis checkpointer: {redis_url}")
        return RedisSaver.from_conn_string(redis_url)

    # In development, use in-memory
    logger.info("💾 Using in-memory checkpointer (MemorySaver)")
    return MemorySaver()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_workflow_config(user_id: str, session_id: str) -> Dict[str, Any]:
    """
    Create LangGraph configuration for a workflow run.

    Args:
        user_id: User ID
        session_id: Session ID

    Returns:
        Config dictionary for graph.invoke()
    """
    return {
        "configurable": {
            "thread_id": f"{user_id}:{session_id}",
            "checkpoint_id": session_id
        }
    }


def should_continue(state: HRMSState) -> str:
    """
    Determine if workflow should continue or end.

    Args:
        state: Current workflow state

    Returns:
        "continue" or "end"
    """
    if state.get("ready_to_execute", False):
        return "end"

    if state.get("next_action"):
        return "continue"

    return "end"


def route_by_intent(state: HRMSState) -> str:
    """
    Route to appropriate workflow based on intent.

    Args:
        state: Current workflow state

    Returns:
        Node name to route to
    """
    intent = state.get("intent", "unknown")

    routing_map = {
        "apply_leave": "leave_workflow",
        "apply_regularization": "regularization_workflow",
        "apply_onduty": "onduty_workflow",
        "check_leave_balance": "balance_query",
        "get_holidays": "holiday_query",
        "get_salary_slip": "salary_slip_query",
        "mark_attendance": "attendance_marking",
        "policy_question": "policy_chat"
    }

    return routing_map.get(intent, "unknown_intent_handler")


def requires_approval(state: HRMSState) -> str:
    """
    Check if state requires approval.

    Args:
        state: Current workflow state

    Returns:
        "approval_required" or "proceed"
    """
    if state.get("requires_approval", False):
        return "approval_required"
    return "proceed"


# ============================================================================
# WORKFLOW BUILDER
# ============================================================================

def build_base_graph() -> StateGraph:
    """
    Build base HRMS workflow graph.

    This is the main entry point for all HRMS operations.

    Returns:
        Compiled StateGraph with checkpointing
    """
    # Create graph
    graph = StateGraph(HRMSState)

    # Add nodes (will be implemented in workflow-specific files)
    from services.ai.workflows.intent_extraction import extract_intent_node
    from services.ai.workflows.validation import validate_data_node
    from services.ai.workflows.execution import execute_action_node
    from services.ai.workflows.response import generate_response_node

    graph.add_node("extract_intent", extract_intent_node)
    graph.add_node("validate_data", validate_data_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("generate_response", generate_response_node)

    # Set entry point
    graph.set_entry_point("extract_intent")

    # Add edges
    graph.add_edge("extract_intent", "validate_data")

    # Conditional routing after validation
    graph.add_conditional_edges(
        "validate_data",
        should_continue,
        {
            "continue": "generate_response",
            "end": "execute_action"
        }
    )

    graph.add_edge("execute_action", "generate_response")
    graph.add_edge("generate_response", END)

    # Compile with checkpointer
    checkpointer = get_checkpointer()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    logger.info("✅ Base HRMS workflow graph compiled")
    return compiled_graph


# ============================================================================
# VISUALIZATION
# ============================================================================

def visualize_workflow(graph: StateGraph, output_path: str = "workflow_graph.png"):
    """
    Visualize LangGraph workflow as PNG.

    Args:
        graph: Compiled StateGraph
        output_path: Path to save PNG file
    """
    try:
        from IPython.display import Image, display

        # Generate graph visualization
        graph_image = graph.get_graph().draw_mermaid_png()

        # Save to file
        with open(output_path, 'wb') as f:
            f.write(graph_image)

        logger.info(f"✅ Workflow visualization saved to {output_path}")

        # Display in Jupyter if available
        try:
            display(Image(graph_image))
        except:
            pass

    except Exception as e:
        logger.warning(f"⚠️ Could not visualize workflow: {e}")
        logger.info("💡 Install graphviz for workflow visualization: pip install pygraphviz")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Basic workflow execution
------------------------------------
from services.ai.langgraph_config import build_base_graph, create_workflow_config

# Build graph
graph = build_base_graph()

# Create initial state
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
    "ready_to_execute": False
}

# Run workflow
config = create_workflow_config("240611", "sess123")
result = graph.invoke(initial_state, config)

print(result["response"])


Example 2: Stream workflow steps
---------------------------------
# Stream each step of the workflow
for state in graph.stream(initial_state, config):
    print(f"Step: {state['current_step']}")
    print(f"Response: {state.get('response', '')}")


Example 3: Resume from checkpoint
----------------------------------
# First run
result1 = graph.invoke(initial_state, config)

# Later, resume from same checkpoint
result2 = graph.invoke(
    {"user_message": "sick leave", "user_id": "240611", "session_id": "sess123"},
    config  # Same config = same checkpoint
)


Example 4: Visualize workflow
------------------------------
from services.ai.langgraph_config import build_base_graph, visualize_workflow

graph = build_base_graph()
visualize_workflow(graph, "hrms_workflow.png")
"""


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'HRMSState',
    'LeaveApplicationState',
    'RegularizationState',
    'OnDutyState',
    'build_base_graph',
    'create_workflow_config',
    'get_checkpointer',
    'visualize_workflow',
    'should_continue',
    'route_by_intent',
    'requires_approval'
]
