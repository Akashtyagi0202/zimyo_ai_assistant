"""
AI Services - LLM, Embeddings, Agents, and Tools
"""

# Core AI services (always available)
from services.ai.chat import get_chat_response, create_description
from services.ai.embeddings import generate_embeddings, similarity_search

# Agent and tools (optional - only imported when needed)
# from services.ai.agent import HRMSAgent, get_agent
# from services.ai.tools import get_hrms_tools, HRMSToolkit

__all__ = [
    'get_chat_response',
    'create_description',
    'generate_embeddings',
    'similarity_search',
    # 'HRMSAgent',
    # 'get_agent',
    # 'get_hrms_tools',
    # 'HRMSToolkit',
]
