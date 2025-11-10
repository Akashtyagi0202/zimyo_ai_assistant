"""
Login Handler

Handles user login flow including:
- User data retrieval
- Policy extraction and processing
- Embedding generation
- Session storage in Redis

This module encapsulates all login business logic,
keeping app.py clean and focused on routing.
"""

import logging
import json
from typing import Dict, Any

from .auth import get_partner_token
from .employee import retrieve_user_data
from .policy import extract_policies, process_pdfs_concurrently
from services.ai.embeddings import generate_embeddings

logger = logging.getLogger(__name__)


def get_last_dates() -> Dict[str, str]:
    """
    Get default date range for user data retrieval.

    Returns:
        Dictionary with from_date and to_date
    """
    return {"from_date": "2025-01-01", "to_date": "2025-12-31"}


async def handle_login(
    user_id: str,
    role: str,
    user_token: str,
    redis_client,
    embedding_model
) -> Dict[str, Any]:
    """
    Handle complete login flow for a user.

    Process:
    1. Authenticate with partner token
    2. Retrieve user data from Zimyo API
    3. Extract and process policy PDFs
    4. Generate embeddings for policies
    5. Store session in Redis

    Args:
        user_id: Employee ID
        role: User role (employee/manager)
        user_token: User authentication token
        redis_client: Redis client instance
        embedding_model: Sentence transformer model for embeddings

    Returns:
        Dictionary with login result:
        {
            "message": "Login successful",
            "userId": str,
            "role": str,
            "policies_count": int
        }

    Raises:
        Exception: If user data retrieval or processing fails
    """
    logger.info(f"🔐 Login attempt for userId={user_id}, role={role}")

    # Step 1: Get partner token for API authentication
    token = get_partner_token()
    time_period = get_last_dates()

    # Step 2: Retrieve user data from Zimyo API
    logger.debug(f"📥 Fetching user data for {user_id}")
    user_data = retrieve_user_data(user_id, time_period, token)
    user_data = user_data['data']

    # Step 3: Extract policy PDFs from user data
    logger.debug(f"📄 Extracting policies for {user_id}")
    policies_file_data = extract_policies(user_data.pop('policyLists'))

    # Step 4: Process PDFs concurrently (performance optimization)
    logger.debug(f"🔄 Processing {len(policies_file_data)} policy PDFs")
    policy_files_text = process_pdfs_concurrently(policies_file_data=policies_file_data)

    # Step 5: Generate embeddings for each policy
    logger.debug(f"🧮 Generating embeddings for policies")
    policy_embeddings = {}
    for policy_name, policy_text in policy_files_text.items():
        embedding = generate_embeddings(embedding_model, policy_text)
        if embedding is not None:
            # Convert numpy array to list for JSON serialization
            policy_embeddings[policy_name] = embedding.tolist()

    logger.info(f"✅ Policy data processed for user {user_id}: {len(policy_embeddings)} policies")

    # Step 6: Create session object
    session_obj = {
        "userId": user_id,
        "role": role,
        "user_info": user_data,
        "token": user_token,
        "user_policies": policy_files_text,
        "policy_embeddings": policy_embeddings
    }

    # Step 7: Store session in Redis
    redis_client.set(user_id, json.dumps(session_obj))
    logger.info(f"💾 Session stored in Redis for user {user_id}")

    return {
        "message": "Login successful",
        "userId": user_id,
        "role": role,
        "policies_count": len(policy_files_text)
    }
