"""
Multi-Operation AI System for HRMS
Advanced command processing with role-based access control and operation routing
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from enum import Enum
from services.assistants.hrms_assistant import Intent, Role, OperationType, HRMSAIAssistant

logger = logging.getLogger(__name__)

@dataclass
class OperationConfig:
    """Configuration for each operation"""
    intent: Intent
    operation_type: OperationType
    required_roles: Set[Role]
    confirmation_required: bool = False
    parameters_required: List[str] = None
    estimated_time: str = "1-2 minutes"

@dataclass
class OperationResult:
    """Result of operation execution"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    operation_id: Optional[str] = None
    estimated_completion: Optional[str] = None
    next_steps: Optional[List[str]] = None

class MultiOperationAI:
    """Advanced multi-operation AI system with role-based access control"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.ai_assistant = HRMSAIAssistant(redis_client)
        self.operation_configs = self._initialize_operation_configs()
        self.active_operations = {}  # Track running operations

    def _initialize_operation_configs(self) -> Dict[Intent, OperationConfig]:
        """Initialize operation configurations with role-based access control"""
        return {
            # Employee Operations
            Intent.POLICY_QUERY: OperationConfig(
                intent=Intent.POLICY_QUERY,
                operation_type=OperationType.QUERY,
                required_roles={Role.EMPLOYEE, Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN}
            ),
            Intent.APPLY_LEAVE: OperationConfig(
                intent=Intent.APPLY_LEAVE,
                operation_type=OperationType.ACTION,
                required_roles={Role.EMPLOYEE, Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN},
                parameters_required=["dates", "leave_type"]
            ),
            Intent.MARK_ATTENDANCE: OperationConfig(
                intent=Intent.MARK_ATTENDANCE,
                operation_type=OperationType.ACTION,
                required_roles={Role.EMPLOYEE, Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN}
            ),
            Intent.CHECK_LEAVE_BALANCE: OperationConfig(
                intent=Intent.CHECK_LEAVE_BALANCE,
                operation_type=OperationType.QUERY,
                required_roles={Role.EMPLOYEE, Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN}
            ),

            # Admin Operations - Employee Management
            Intent.SEND_OFFER_LETTER: OperationConfig(
                intent=Intent.SEND_OFFER_LETTER,
                operation_type=OperationType.ADMIN_ACTION,
                required_roles={Role.HR_ADMIN, Role.SUPER_ADMIN},
                parameters_required=["employee_code", "position"],
                estimated_time="2-3 minutes"
            ),
            Intent.APPROVE_LEAVE: OperationConfig(
                intent=Intent.APPROVE_LEAVE,
                operation_type=OperationType.ADMIN_ACTION,
                required_roles={Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN},
                parameters_required=["leave_request_id"]
            ),

            # Admin Operations - Reports & Analytics
            Intent.GENERATE_ATTENDANCE_REPORT: OperationConfig(
                intent=Intent.GENERATE_ATTENDANCE_REPORT,
                operation_type=OperationType.QUERY,
                required_roles={Role.MANAGER, Role.HR_ADMIN, Role.SUPER_ADMIN},
                parameters_required=["month", "year"],
                estimated_time="3-5 minutes"
            ),
        }

    async def process_command(self, user_id: str, command: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for processing AI commands"""
        try:
            # Get user context
            user_context = await self._get_user_context(user_id)
            if not user_context:
                return {"error": "User not logged in. Please login first."}

            # Detect intent using AI assistant
            ai_result = await self.ai_assistant.process_query(user_id, command)

            if ai_result.get("error"):
                return ai_result

            # Check if it requires clarification
            if ai_result.get("requires_clarification"):
                return ai_result

            # Get intent and check access
            intent_str = ai_result.get("intent")
            try:
                intent = Intent(intent_str)
            except ValueError:
                return {"error": f"Unknown intent: {intent_str}"}

            # Check role-based access
            access_check = self._check_access(user_context["role"], intent)
            if not access_check["allowed"]:
                return {
                    "error": f"Access denied. {access_check['message']}",
                    "required_role": access_check.get("required_roles"),
                    "current_role": user_context["role"]
                }

            # Route to appropriate handler
            return await self._route_operation(intent, ai_result, user_context, command, session_id)

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return {"error": "Failed to process command. Please try again."}

    def _check_access(self, user_role: str, intent: Intent) -> Dict[str, Any]:
        """Check if user has access to perform the operation"""
        try:
            user_role_enum = Role(user_role.lower())
        except ValueError:
            return {"allowed": False, "message": f"Invalid user role: {user_role}"}

        operation_config = self.operation_configs.get(intent)
        if not operation_config:
            return {"allowed": False, "message": f"Operation not configured: {intent.value}"}

        if user_role_enum in operation_config.required_roles:
            return {"allowed": True}
        else:
            required_roles = [role.value for role in operation_config.required_roles]
            return {
                "allowed": False,
                "message": f"Insufficient permissions. Required roles: {required_roles}",
                "required_roles": required_roles
            }

    async def _route_operation(self, intent: Intent, ai_result: Dict[str, Any], user_context: Dict[str, Any],
                              command: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Route operation to appropriate handler"""

        operation_config = self.operation_configs[intent]

        # Check if confirmation is required for sensitive operations
        if operation_config.confirmation_required and not ai_result.get("confirmed"):
            return await self._request_confirmation(intent, ai_result, operation_config)

        # Route to specific handlers
        handler_map = {
            # Employee operations (route to existing systems)
            Intent.POLICY_QUERY: self._handle_employee_operation,  # Generic policy queries
            Intent.APPLY_LEAVE: self._handle_employee_operation,
            Intent.MARK_ATTENDANCE: self._handle_employee_operation,
            Intent.CHECK_LEAVE_BALANCE: self._handle_employee_operation,

            # Admin operations (new handlers)
            Intent.SEND_OFFER_LETTER: self._handle_send_offer_letter,
            Intent.APPROVE_LEAVE: self._handle_approve_leave,
            Intent.GENERATE_ATTENDANCE_REPORT: self._handle_generate_attendance_report,
        }

        handler = handler_map.get(intent)
        if handler:
            return await handler(ai_result, user_context, command, session_id)
        else:
            return {"error": f"No handler configured for operation: {intent.value}"}

    async def _request_confirmation(self, intent: Intent, ai_result: Dict[str, Any],
                                   operation_config: OperationConfig) -> Dict[str, Any]:
        """Request confirmation for sensitive operations"""
        return {
            "confirmation_required": True,
            "intent": intent.value,
            "message": f"⚠️ This will {intent.value.replace('_', ' ')}. This action cannot be undone.",
            "operation_details": {
                "estimated_time": operation_config.estimated_time,
                "operation_type": operation_config.operation_type.value,
                "extracted_parameters": ai_result.get("extracted_entities", {})
            },
            "confirmation_text": f"Type 'CONFIRM {intent.value.upper()}' to proceed or 'CANCEL' to abort."
        }

    async def _handle_employee_operation(self, ai_result: Dict[str, Any], user_context: Dict[str, Any],
                                        command: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle employee operations by routing to existing systems"""

        # Route ALL employee operations to HRMS integration for proper handling
        try:
            from services.integration.hrms_integration import process_hrms_query
            return await process_hrms_query(self.redis_client, user_context["userId"], command, session_id)
        except Exception as e:
            logger.error(f"Error in HRMS integration: {e}")
            return {
                "response": "I'll help you with that. Let me process your request.",
                "intent": ai_result.get("intent", "unknown"),
                "confidence": ai_result.get("confidence", 0.7),
                "language": ai_result.get("language", "english")
            }

    # ===================== FUTURE OPERATION HANDLERS =====================
    # Pattern for adding new admin operations - implement only when needed

    async def _handle_send_offer_letter(self, ai_result: Dict[str, Any], user_context: Dict[str, Any],
                                       command: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle offer letter sending - placeholder for future implementation"""
        return {
            "response": "Offer letter generation feature will be implemented soon. Please contact HR admin for manual processing.",
            "intent": ai_result.get("intent", "send_offer_letter"),
            "confidence": ai_result.get("confidence", 0.9),
            "language": ai_result.get("language", "english"),
            "feature_status": "coming_soon"
        }

    async def _handle_approve_leave(self, ai_result: Dict[str, Any], user_context: Dict[str, Any],
                                   command: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle leave approval - route to existing system"""
        return {
            "use_existing_leave_system": True,
            "action": "approve_leave",
            "ai_intent": ai_result["intent"],
            "ai_confidence": ai_result["confidence"],
            "extracted_entities": ai_result.get("extracted_entities", {})
        }

    async def _handle_generate_attendance_report(self, ai_result: Dict[str, Any], user_context: Dict[str, Any],
                                                command: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle attendance report generation - placeholder for future implementation"""
        return {
            "response": "Attendance report generation feature will be implemented soon. Please contact admin for manual processing.",
            "intent": ai_result.get("intent", "generate_attendance_report"),
            "confidence": ai_result.get("confidence", 0.9),
            "language": ai_result.get("language", "english"),
            "feature_status": "coming_soon"
        }

    async def _get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user context from Redis"""
        try:
            user_data_raw = self.redis_client.get(user_id)
            if user_data_raw:
                return json.loads(user_data_raw)
            return None
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return None

    # ===================== HELPER METHODS =====================
    # These will be implemented when actual features are added

    def _extract_month_from_command(self, command: str) -> Optional[str]:
        """Extract month from command text - for future use"""
        months = ["january", "february", "march", "april", "may", "june",
                 "july", "august", "september", "october", "november", "december"]
        command_lower = command.lower()
        for month in months:
            if month in command_lower:
                return month.title()
        return None

    def _extract_employee_code_from_command(self, command: str) -> Optional[str]:
        """Extract employee code from command text - for future use"""
        import re
        patterns = [
            r'\b(emp|employee)\s*(code\s*)?([a-z0-9]+)\b',
            r'\b([a-z]{3}\d{3,})\b',
            r'\bcode\s+([a-z0-9]+)\b'
        ]
        command_lower = command.lower()
        for pattern in patterns:
            match = re.search(pattern, command_lower)
            if match:
                return match.groups()[-1].upper()
        return None

# Convenience function for easy integration
async def process_multi_operation_command(redis_client, user_id: str, command: str,
                                        session_id: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function for processing multi-operation commands"""
    multi_op_system = MultiOperationAI(redis_client)
    return await multi_op_system.process_command(user_id, command, session_id)