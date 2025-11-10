# services/employee_service.py
import requests
import logging
from fastapi import HTTPException
from config import EMPLOYEE_URL

logger = logging.getLogger(__name__)

def retrieve_user_data(user_id: str, time_period: dict, token: str):
    headers = {"token": token}
    params = {
        "from_date": time_period["from_date"],
        "to_date": time_period["to_date"],
        "employee_id": user_id
    }

    try:
        resp = requests.get(EMPLOYEE_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.exception("Failed to fetch employee data for %s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve employee details: {e}")
