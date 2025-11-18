"""
HRMS Workflow Orchestrator with LangGraph

Main entry point for all HRMS workflows using LangGraph.
This module replaces the manual flow with state-machine based workflows.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional

# LangGraph imports
from langgraph.graph import StateGraph

# Local imports
from services.ai.langgraph_config import (
    HRMSState,
    LeaveApplicationState,
    build_base_graph,
    create_workflow_config
)
from services.ai.workflows.leave_approval_workflow import build_leave_approval_workflow

logger = logging.getLogger(__name__)


# ============================================================================
# WORKFLOW REGISTRY
# ============================================================================

class WorkflowOrchestrator:
    """
    Centralized orchestrator for all HRMS workflows.

    Manages workflow creation, execution, and state persistence.
    """

    def __init__(self):
        """Initialize workflow orchestrator."""
        self.workflows = {}
        self._initialize_workflows()

    def _initialize_workflows(self):
        """Initialize all available workflows."""
        logger.info("🏗️ Initializing HRMS workflows...")

        # Basic workflow for simple operations
        self.workflows["base"] = build_base_graph()

        # Advanced leave approval workflow
        self.workflows["leave_approval"] = build_leave_approval_workflow()

        logger.info(f"✅ Initialized {len(self.workflows)} workflows")

    def get_workflow(self, workflow_type: str = "base") -> StateGraph:
        """
        Get compiled workflow by type.

        Args:
            workflow_type: Type of workflow (base, leave_approval, etc.)

        Returns:
            Compiled StateGraph
        """
        workflow = self.workflows.get(workflow_type)
        if not workflow:
            logger.warning(f"⚠️ Workflow '{workflow_type}' not found, using base")
            return self.workflows["base"]
        return workflow

    def determine_workflow_type(self, intent: str) -> str:
        """
        Determine which workflow to use based on intent.

        Args:
            intent: Detected intent

        Returns:
            Workflow type name
        """
        # Use advanced workflows for complex operations
        if intent == "apply_leave":
            return "leave_approval"

        # Use base workflow for simple operations
        return "base"

    async def process_message(
        self,
        user_id: str,
        user_message: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user message through appropriate workflow.

        This is the MAIN ENTRY POINT for LangGraph-based processing.

        Args:
            user_id: User ID
            user_message: User's message
            session_id: Session ID for state persistence

        Returns:
            Response dictionary with workflow result
        """
        session_id = session_id or "default"

        logger.info(f"🎬 Processing message for user {user_id}, session {session_id}")

        try:
            # Step 1: Quick intent detection to choose workflow
            # Use existing working extractor
            from services.ai.hrms_extractor import detect_intent_and_extract

            quick_result = detect_intent_and_extract(user_message, {}, [])
            intent = quick_result.get("intent", "unknown")

            logger.info(f"🎯 Detected intent: {intent}")

            # Step 2: Select appropriate workflow
            workflow_type = self.determine_workflow_type(intent)
            workflow = self.get_workflow(workflow_type)

            logger.info(f"📊 Using workflow: {workflow_type}")

            # Step 3: Create initial state
            initial_state = self._create_initial_state(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                workflow_type=workflow_type
            )

            # Step 4: Create workflow config
            config = create_workflow_config(user_id, session_id)

            # Step 5: Execute workflow
            logger.info("⚡ Executing workflow...")
            result = workflow.invoke(initial_state, config)

            logger.info(f"✅ Workflow completed: {result.get('current_step')}")

            # Step 6: Extract response
            return {
                "response": result.get("response", "I didn't understand that."),
                "sessionId": session_id,
                "intent": result.get("intent"),
                "ready_to_execute": result.get("ready_to_execute", False),
                "workflow_type": workflow_type,
                "current_step": result.get("current_step")
            }

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}", exc_info=True)
            return {
                "response": f"Sorry, an error occurred: {str(e)}",
                "sessionId": session_id,
                "error": str(e)
            }

    def _create_initial_state(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        workflow_type: str
    ) -> Dict[str, Any]:
        """
        Create initial state for workflow.

        Args:
            user_id: User ID
            session_id: Session ID
            user_message: User message
            workflow_type: Type of workflow

        Returns:
            Initial state dictionary
        """
        # Base state
        base_state = {
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
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

        # Add workflow-specific fields
        if workflow_type == "leave_approval":
            base_state.update({
                "leave_type": None,
                "from_date": None,
                "to_date": None,
                "reason": None,
                "leave_balance": None,
                "has_sufficient_balance": False,
                "alternative_suggestions": []
            })

        return base_state

    def visualize_workflow(self, workflow_type: str = "base", output_path: str = None):
        """
        Visualize workflow as PNG.

        Args:
            workflow_type: Type of workflow to visualize
            output_path: Path to save PNG (default: {workflow_type}_workflow.png)
        """
        from services.ai.langgraph_config import visualize_workflow

        workflow = self.get_workflow(workflow_type)
        output_path = output_path or f"{workflow_type}_workflow.png"

        visualize_workflow(workflow, output_path)
        logger.info(f"✅ Workflow visualization saved to {output_path}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_orchestrator_instance = None


def get_orchestrator() -> WorkflowOrchestrator:
    """
    Get singleton workflow orchestrator instance.

    Returns:
        WorkflowOrchestrator instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = WorkflowOrchestrator()

    return _orchestrator_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def process_hrms_message(
    user_id: str,
    user_message: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process HRMS message using LangGraph workflows.

    This is the main entry point to use from app.py

    Args:
        user_id: User ID
        user_message: User's message
        session_id: Session ID (optional)

    Returns:
        Response dictionary
    """
    orchestrator = get_orchestrator()
    return await orchestrator.process_message(user_id, user_message, session_id)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'WorkflowOrchestrator',
    'get_orchestrator',
    'process_hrms_message'
]


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Use from app.py (async route)
-----------------------------------------
from services.ai.hrms_workflow_orchestrator import process_hrms_message

@app.post("/chat")
async def chat(request: ChatRequest):
    result = await process_hrms_message(
        user_id=request.userId,
        user_message=request.message,
        session_id=request.sessionId
    )

    return {"response": result["response"], "sessionId": result["sessionId"]}


Example 2: Direct orchestrator usage
-------------------------------------
from services.ai.hrms_workflow_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Process message
result = await orchestrator.process_message(
    user_id="240611",
    user_message="apply sick leave for tomorrow",
    session_id="sess123"
)

print(result["response"])


Example 3: Visualize workflows
-------------------------------
from services.ai.hrms_workflow_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Visualize leave approval workflow
orchestrator.visualize_workflow("leave_approval", "leave_workflow.png")

# Visualize base workflow
orchestrator.visualize_workflow("base", "base_workflow.png")


Example 4: Multi-turn conversation
-----------------------------------
orchestrator = get_orchestrator()

# First message
result1 = await orchestrator.process_message(
    user_id="240611",
    user_message="apply leave",
    session_id="sess123"
)
print(result1["response"])  # "What type of leave?"

# Second message (continues from checkpoint)
result2 = await orchestrator.process_message(
    user_id="240611",
    user_message="sick leave",
    session_id="sess123"  # Same session = continues from previous state
)
print(result2["response"])  # "For which date?"

# Third message
result3 = await orchestrator.process_message(
    user_id="240611",
    user_message="tomorrow, not feeling well",
    session_id="sess123"
)
print(result3["response"])  # "Leave applied successfully!"
"""
