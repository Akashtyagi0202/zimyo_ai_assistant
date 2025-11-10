# storage/session_storage.py
import json
import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

# decode_responses=True -> returns str instead of bytes
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def set_session(user_id: str, data: dict, expire_seconds: int = None):
    payload = json.dumps(data)
    if expire_seconds:
        redis_client.setex(user_id, expire_seconds, payload)
    else:
        redis_client.set(user_id, payload)

def get_session(user_id: str):
    val = redis_client.get(user_id)
    return json.loads(val) if val else None

def delete_session(user_id: str):
    redis_client.delete(user_id)
