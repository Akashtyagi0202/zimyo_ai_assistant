"""
AI Agent for Autonomous HRMS Operations
Foundation for future complete HRMS/Payroll automation

This module provides an AI agent that can:
- Understand user requests in natural language
- Automatically decide which HRMS operations to perform
- Execute multi-step workflows autonomously
- Handle complex HRMS/Payroll tasks via conversation

Future capabilities (when enabled):
- Complete payroll processing via conversation
- Autonomous policy compliance checking
- Multi-step approval workflows
- Complex salary calculations and adjustments

Usage:
    from ai_agent import HRMSAgent

    agent = HRMSAgent(user_id="emp123")
    response = await agent.process_request("I want to apply for leave next Monday")
    # Agent will automatically: detect intent → validate dates → apply leave
"""

import logging
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# OpenAI for LLM (direct SDK)
from openai import OpenAI

# LangChain for agent capabilities
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# Our HRMS tools
from services.ai.tools import get_hrms_tools

load_dotenv()
logger = logging.getLogger(__name__)

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

class HRMSAgent:
    """
    AI Agent for autonomous HRMS operations

    This agent can understand natural language requests and autonomously
    execute HRMS operations using the available tools.

    Features:
    - Natural language understanding
    - Multi-step task execution
    - Conversational memory (remembers context)
    - Tool usage (marks attendance, applies leave, etc.)
    - Error handling and recovery

    Example:
        agent = HRMSAgent("emp123")
        response = await agent.process_request("Apply casual leave for tomorrow")
        # Agent automatically handles the entire workflow
    """

    def __init__(
        self,
        user_id: str,
        enable_memory: bool = True,
        temperature: float = 0.7,
        verbose: bool = False
    ):
        """
        Initialize HRMS AI Agent

        Args:
            user_id: Employee ID for whom agent operates
            enable_memory: Enable conversation memory (default: True)
            temperature: LLM temperature for creativity (0.0-1.0)
            verbose: Enable verbose logging (default: False)
        """
        self.user_id = user_id
        self.enable_memory = enable_memory
        self.verbose = verbose

        # Initialize LLM (LangChain wrapper for agent features)
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=2048
        )

        # Get HRMS tools for this user
        self.tools = get_hrms_tools(user_id)

        # Setup agent prompt
        self.prompt = self._create_agent_prompt()

        # Setup memory (if enabled)
        self.memory = None
        if enable_memory:
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )

        # Create agent
        self.agent = self._create_agent()

        logger.info(f"HRMSAgent initialized for user {user_id} with {len(self.tools)} tools")

    def _create_agent_prompt(self) -> ChatPromptTemplate:
        """
        Create the system prompt for the HRMS agent

        Defines the agent's personality, capabilities, and behavior
        """
        system_message = """You are a helpful HRMS (Human Resource Management System) AI assistant.

Your role is to help employees with their HR-related tasks such as:
- Marking attendance
- Applying for leaves
- Checking leave balance
- Getting information about leave types
- Validating leave requests

IMPORTANT GUIDELINES:
1. Always be professional and friendly
2. When applying for leave, make sure you have all required information:
   - Leave type (ask user to choose from available types if not specified)
   - Start date and end date (in YYYY-MM-DD format)
   - Reason for leave
3. Before applying leave, consider validating it first to check if it's allowed
4. If user provides dates in natural language (like "tomorrow", "next Monday"), convert them to YYYY-MM-DD format
5. Always confirm actions before executing them
6. If you're unsure about something, ask the user for clarification
7. Provide clear, concise responses

You have access to tools to perform these operations. Use them wisely to help the employee.
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        return prompt

    def _create_agent(self) -> AgentExecutor:
        """
        Create the LangChain agent executor

        Uses OpenAI Functions agent for better tool calling
        """
        # Create agent
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # Create executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=self.verbose,
            max_iterations=5,  # Prevent infinite loops
            early_stopping_method="generate",  # Generate response even if max iterations reached
            handle_parsing_errors=True  # Gracefully handle parsing errors
        )

        return agent_executor

    async def process_request(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user request using the AI agent

        The agent will:
        1. Understand the user's intent
        2. Decide which tools to use
        3. Execute the necessary operations
        4. Return a natural language response

        Args:
            user_message: User's natural language request

        Returns:
            Dict with:
            - response: Agent's response text
            - success: Whether operation was successful
            - tools_used: List of tools that were invoked (optional)

        Example:
            result = await agent.process_request("Apply casual leave for tomorrow because I'm sick")
            print(result["response"])
        """
        try:
            logger.info(f"Agent processing request for user {self.user_id}: {user_message[:100]}")

            # Invoke agent
            result = await self.agent.ainvoke({
                "input": user_message
            })

            response_text = result.get("output", "I'm sorry, I couldn't process your request.")

            logger.info(f"Agent completed request. Response length: {len(response_text)}")

            return {
                "response": response_text,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            return {
                "response": f"I encountered an error while processing your request: {str(e)}",
                "success": False,
                "error": str(e)
            }

    def clear_memory(self):
        """Clear the agent's conversation memory"""
        if self.memory:
            self.memory.clear()
            logger.info(f"Cleared memory for user {self.user_id}")

    def get_memory_messages(self):
        """Get the current conversation history"""
        if self.memory:
            return self.memory.chat_memory.messages
        return []


# ===================== CONVENIENCE FUNCTIONS =====================

_agent_cache: Dict[str, HRMSAgent] = {}

def get_agent(user_id: str, enable_memory: bool = True) -> HRMSAgent:
    """
    Get or create an HRMS agent for a user

    Uses caching to maintain agent state across requests

    Args:
        user_id: Employee ID
        enable_memory: Enable conversation memory

    Returns:
        HRMSAgent instance
    """
    cache_key = f"{user_id}_{enable_memory}"

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = HRMSAgent(
            user_id=user_id,
            enable_memory=enable_memory
        )

    return _agent_cache[cache_key]

def clear_agent_cache(user_id: Optional[str] = None):
    """
    Clear cached agents

    Args:
        user_id: Specific user ID to clear, or None to clear all
    """
    global _agent_cache

    if user_id:
        # Clear specific user's agents
        keys_to_remove = [k for k in _agent_cache.keys() if k.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del _agent_cache[key]
        logger.info(f"Cleared {len(keys_to_remove)} agents for user {user_id}")
    else:
        # Clear all agents
        count = len(_agent_cache)
        _agent_cache.clear()
        logger.info(f"Cleared all {count} cached agents")


# ===================== EXAMPLE USAGE =====================

async def example_usage():
    """
    Example usage of HRMS Agent
    Uncomment to test
    """
    # Create agent
    agent = HRMSAgent("emp123")

    # Example requests
    requests = [
        "What is my leave balance?",
        "What types of leaves are available?",
        "I want to apply for casual leave tomorrow because I have a doctor's appointment",
        "Mark my attendance"
    ]

    for request in requests:
        print(f"\nUser: {request}")
        result = await agent.process_request(request)
        print(f"Agent: {result['response']}")
        print("-" * 80)

# Uncomment to run example:
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(example_usage())
