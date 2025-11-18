"""
LangChain-based Chat Module for HRMS AI Assistant

This module handles policy Q&A and HR content generation using LangChain.

Improvements over manual implementation:
- Reusable prompt templates
- Better memory management
- LangSmith tracing for debugging
- Structured output handling

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any, Optional

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate

# Local imports
from services.ai.langchain_config import get_llm
from services.ai.langchain_prompts import (
    get_employee_chat_prompt,
    get_hr_content_prompt
)

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN CHAT FUNCTIONS
# ============================================================================

def get_chat_response(
    role: str,
    prompt: str,
    employee_data: str = "",
    policy_content: str = ""
) -> str:
    """
    Get chat response using LangChain for employee or manager queries.

    Args:
        role: User role ("employee" or "manager")
        prompt: User's query/message
        employee_data: Employee information context (optional)
        policy_content: Relevant policy documents (optional)

    Returns:
        AI-generated response text
    """
    try:
        # Get LLM
        llm = get_llm(temperature=0.7)  # Higher temp for creative responses

        # Select appropriate prompt based on role
        if role == "manager":
            prompt_template = get_hr_content_prompt()
            chain = prompt_template | llm

            response = chain.invoke({
                "query": prompt,
                "employee_data": employee_data or "No employee data provided",
                "policy_content": policy_content or "No policy context provided"
            })

        else:  # employee
            prompt_template = get_employee_chat_prompt()
            chain = prompt_template | llm

            response = chain.invoke({
                "query": prompt,
                "employee_data": employee_data or "No employee data provided",
                "policy_content": policy_content or "No policy context provided"
            })

        logger.info(f"✅ LangChain chat response generated for role: {role}")
        return response.content

    except Exception as e:
        logger.error(f"❌ LangChain chat failed: {e}")
        return f"Error getting response: {str(e)}"


def create_description(prompt: str) -> str:
    """
    Generate a short 3-5 word description for the given prompt using LangChain.

    Args:
        prompt: User query to generate description for

    Returns:
        Short 3-5 word description
    """
    try:
        llm = get_llm(temperature=0.3)  # Low temp for consistent descriptions

        description_prompt = ChatPromptTemplate.from_messages([
            ("system", "You must generate a short 3-5 word prompt for a query given by a user."),
            ("human", "{query}")
        ])

        chain = description_prompt | llm

        response = chain.invoke({"query": prompt})

        logger.info(f"✅ Description generated: {response.content[:50]}")
        return response.content.strip()

    except Exception as e:
        logger.error(f"❌ Description generation failed: {e}")
        return f"Error: {str(e)}"


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

# Keep the same exports for existing code
__all__ = ['get_chat_response', 'create_description']


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Employee policy question
------------------------------------
from services.ai.chat_langchain import get_chat_response

employee_data = "Name: Akash, Sick Leave: 3.72 days, Casual Leave: 2.72 days"
policy_content = "Employees can take sick leave with medical certificate after 3 days..."

response = get_chat_response(
    role="employee",
    prompt="How many sick leaves do I have remaining?",
    employee_data=employee_data,
    policy_content=policy_content
)

print(response)


Example 2: Manager HR content generation
-----------------------------------------
response = get_chat_response(
    role="manager",
    prompt="Create a job description for Senior Python Developer position",
    employee_data="",
    policy_content="Our company values: Innovation, Collaboration, Excellence..."
)

print(response)


Example 3: Generate description
--------------------------------
description = create_description("How do I apply for work from home?")
print(description)  # "WFH Application Process"
"""
