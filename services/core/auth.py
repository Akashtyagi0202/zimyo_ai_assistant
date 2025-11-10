# services/auth_service.py
import requests
import logging
from fastapi import HTTPException
from config import PARTNER_SECRET, PARTNER_ID, CLIENT_CODE, AUTH_KEY, TOKEN_URL

logger = logging.getLogger(__name__)

# Simple caching in-memory token — you can move to Redis later
_cached_token = None
_cached_token_expiry = 0


def get_partner_token():
    global _cached_token, _cached_token_expiry
    # For demo: always request a token. In prod: cache until expiry.

    headers = {
        "x-forwarded-for": "127.0.0.1",
        "User-Agent": "ZimyoAI/1.0",
        "Authorization": AUTH_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "partner_secret": PARTNER_SECRET,
        "partner_id": PARTNER_ID,
        "client_code": CLIENT_CODE,
    }

    try:
        logger.debug("Requesting partner token from %s", TOKEN_URL)
        resp = requests.post(TOKEN_URL, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        logger.debug("Partner token response: %s", body)

        token = body.get("data", {}).get("token")
        if not token:
            logger.error("Token not present in response: %s", body)
            raise HTTPException(status_code=500, detail="Token missing in response")

        logger.info("Successfully fetched partner token")
        return token

    except Exception as e:
        logger.exception("Failed to fetch partner token")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve token: {e}")
