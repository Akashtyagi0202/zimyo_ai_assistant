# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Zimyo API config (keep secrets in .env in production)
PARTNER_SECRET = os.getenv("PARTNER_SECRET", "9Rcn+AQ{l.hV2Wvnsls#4G")
PARTNER_ID = int(os.getenv("PARTNER_ID", 228602))
CLIENT_CODE = os.getenv("CLIENT_CODE", "ZIMYO")
AUTH_KEY = os.getenv("AUTH_KEY", "25a20c3e-beb6-11ed-9234-0123456789ab")

TOKEN_URL = os.getenv("TOKEN_URL", "https://apiserver.zimyo.com/apiv1/v1/token")
EMPLOYEE_URL = os.getenv("EMPLOYEE_URL", "https://apiserver.zimyo.com/apiv1/v1/org/employee-details")

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
