"""
Operation Handlers - Simple functions for each HR operation
Easy to understand and maintain
"""

import logging
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ===================== SIMPLE OPERATION HANDLERS =====================

async def try_multi_operation_system(redis_client, user_id: str, user_prompt: str, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Try processing with multi-operation AI system"""
    try:
        from services.operations.multi_operation import process_multi_operation_command

        result = await process_multi_operation_command(redis_client, user_id, user_prompt, session_id)

        # Check if it handled successfully
        # Don't return result if it requires clarification - let conversation continuation try
        if not result.get("error") and not result.get("use_existing_leave_system") and not result.get("requires_clarification"):
            logger.info(f"Multi-operation system handled: {user_prompt[:50]}...")
            if session_id and "sessionId" not in result:
                result["sessionId"] = session_id
            return result

        return None  # Let other handlers try

    except Exception as e:
        logger.error(f"Error in multi-operation system: {e}")
        return None


# ====================================================================
# DEPRECATED FUNCTIONS - Replaced by AI-powered handler
# These functions are kept for backward compatibility only
# New code should use services/operations/ai_handler.py
# ====================================================================

# Old handle_conversation_continuation - DEPRECATED
# Use: services/operations/ai_handler.handle_hrms_with_ai

# Old handle_new_hr_action - DEPRECATED
# Use: services/operations/ai_handler.handle_hrms_with_ai


async def handle_regular_chat(redis_client, user_id: str, user_prompt: str, user_role: str, session_id: Optional[str]) -> Dict[str, Any]:
    """Handle regular chat with policy search and return relevant document links"""
    try:
        # Get user data from Redis
        user_data_raw = redis_client.get(user_id)
        if not user_data_raw:
            error_response = {"response": "User session expired. Please login again."}
            if session_id:
                error_response["sessionId"] = session_id
            return error_response

        user_data = json.loads(user_data_raw)
        user_policies = user_data["user_policies"]
        user_embeddings = user_data["policy_embeddings"]
        user_info = user_data["user_info"]

        # Generate response using policy search (now returns response + relevant policies)
        response, relevant_policies = await generate_policy_response(user_prompt, user_policies, user_embeddings, user_info, user_role)

        response_data = {"response": response}

        # Add relevant policy documents as downloadable resources
        if relevant_policies:
            response_data["resources"] = relevant_policies
            logger.info(f"📎 Attached {len(relevant_policies)} policy document(s) as resources")

        if session_id:
            response_data["sessionId"] = session_id

        return response_data

    except Exception as e:
        logger.error(f"Error in regular chat processing: {e}")
        error_response = {"response": "Error processing your request. Please try again."}
        if session_id:
            error_response["sessionId"] = session_id
        return error_response


async def generate_policy_response(user_prompt: str, user_policies: Dict, user_embeddings: Dict, user_info: Dict, user_role: str):
    """
    Generate response using policy search and AI

    Returns:
        tuple: (response_text, relevant_policies_list)
        - response_text: AI generated response
        - relevant_policies_list: List of dicts with policy info for downloading
    """
    try:
        import numpy as np
        from services.ai.embeddings import similarity_search
        from services.ai.chat import get_chat_response
        from sentence_transformers import SentenceTransformer

        # Load embedding model
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Convert embeddings
        embeddings_numpy = {k: np.array(v) for k, v in user_embeddings.items()}

        # Find relevant policies
        most_relevant_policy = similarity_search(embedding_model, user_prompt, embeddings_numpy)

        # Build prompt
        enriched_prompt = f"EMPLOYEE DETAILS: {user_info}\n\nQUERY: {user_prompt}\n"

        # Track relevant policies for resource links
        relevant_policies_list = []

        if most_relevant_policy:
            for policy_name in most_relevant_policy:
                policy_text = user_policies.get(policy_name, '')
                if policy_text:
                    enriched_prompt += f"\nReference File:\npolicy_name: {policy_name}\npolicy_text: {policy_text}\n"

                    # Add to resources list
                    relevant_policies_list.append({
                        "name": policy_name,
                        "type": "policy_document",
                        "description": f"📄 Reference: {policy_name}"
                    })
        else:
            enriched_prompt += "\nNo relevant policies found in knowledge base."

        # Get AI response
        ai_response = get_chat_response(role=user_role, prompt=enriched_prompt)

        # Append resource info to response if policies were found
        if relevant_policies_list:
            resource_text = "\n\n📎 संबंधित नीति दस्तावेज़। Related Policy Documents:\n"
            for idx, policy in enumerate(relevant_policies_list, 1):
                resource_text += f"{idx}. {policy['name']}\n"
            ai_response += resource_text

        return ai_response, relevant_policies_list

    except Exception as e:
        logger.error(f"Error generating policy response: {e}")
        return "I'm sorry, I encountered an error while searching for information. Please try again.", []


async def handle_user_operation(redis_client, user_id: str, user_prompt: str, user_role: str,
                               session_id: Optional[str] = None, conversation_context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Simple main function to handle any user operation
    Now powered by AI for intelligent intent detection and extraction
    """
    try:
        logger.info(f"Handling operation for user {user_id} with role {user_role}")

        # Step 1: Try LangGraph-powered HRMS workflow (state-machine based workflows)
        from services.ai.hrms_workflow_orchestrator import process_hrms_message

        ai_result = await process_hrms_message(user_id, user_prompt, session_id)
        if ai_result is not None:
            logger.info("✅ LangGraph workflow processed the request")
            return ai_result

        logger.info("AI handler returned None, falling back to other handlers")

        # Step 2: Try multi-operation AI system (admin operations)
        result = await try_multi_operation_system(redis_client, user_id, user_prompt, session_id)
        if result:
            return result

        # Step 3: Regular chat with policy search (for policy questions)
        return await handle_regular_chat(redis_client, user_id, user_prompt, user_role, session_id)

    except Exception as e:
        logger.error(f"Error in handle_user_operation: {e}")
        error_response = {"response": "Sorry, I encountered an error. Please try again."}
        if session_id:
            error_response["sessionId"] = session_id
        return error_response