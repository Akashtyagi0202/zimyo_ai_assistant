#!/usr/bin/env python3
"""
Migration Script: Migrate existing Redis sessions to LangChain format

This script:
1. Scans all existing Redis sessions
2. Converts old format to LangChain RedisChatMessageHistory format
3. Preserves all conversation history
4. Creates backup before migration
5. Validates migration success

Run: python migrate_to_langchain.py

Author: Zimyo AI Team
"""

import redis
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis config
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

# Connect to Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def backup_redis_data():
    """
    Create a backup of all Redis data before migration.
    """
    backup_file = f"redis_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    logger.info("📦 Creating backup...")

    all_keys = redis_client.keys("*")
    backup_data = {}

    for key in all_keys:
        value = redis_client.get(key)
        ttl = redis_client.ttl(key)
        backup_data[key] = {
            "value": value,
            "ttl": ttl
        }

    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2)

    logger.info(f"✅ Backup created: {backup_file} ({len(all_keys)} keys)")
    return backup_file


def find_chat_history_keys() -> List[str]:
    """
    Find all chat history keys in Redis.

    Old format: chat_history:{user_id}:{session_id}
    """
    pattern = "chat_history:*:*"
    keys = redis_client.keys(pattern)
    logger.info(f"🔍 Found {len(keys)} chat history keys")
    return keys


def migrate_chat_history(key: str) -> bool:
    """
    Migrate a single chat history from old format to LangChain format.

    Old format:
    [
        {"role": "user", "message": "hello", "timestamp": "..."},
        {"role": "assistant", "message": "hi", "timestamp": "..."}
    ]

    LangChain format:
    {
        "messages": [
            {"type": "human", "data": {"content": "hello", ...}},
            {"type": "ai", "data": {"content": "hi", ...}}
        ]
    }
    """
    try:
        # Get old data
        old_data_raw = redis_client.get(key)
        if not old_data_raw:
            logger.warning(f"⚠️ Key {key} is empty, skipping")
            return False

        old_data = json.loads(old_data_raw)
        if not isinstance(old_data, list):
            logger.warning(f"⚠️ Key {key} has invalid format, skipping")
            return False

        # Convert to LangChain format
        langchain_messages = []

        for msg in old_data:
            role = msg.get("role")
            content = msg.get("message")
            timestamp = msg.get("timestamp", datetime.now().isoformat())

            if role == "user":
                langchain_messages.append({
                    "type": "human",
                    "data": {
                        "content": content,
                        "additional_kwargs": {},
                        "response_metadata": {},
                        "type": "human",
                        "name": None,
                        "id": None,
                        "example": False
                    }
                })
            elif role == "assistant":
                langchain_messages.append({
                    "type": "ai",
                    "data": {
                        "content": content,
                        "additional_kwargs": {},
                        "response_metadata": {},
                        "type": "ai",
                        "name": None,
                        "id": None,
                        "example": False,
                        "tool_calls": [],
                        "invalid_tool_calls": [],
                        "usage_metadata": None
                    }
                })

        # Create LangChain format
        langchain_data = {
            "messages": langchain_messages
        }

        # Store back to Redis (LangChain will read this format)
        redis_client.set(key, json.dumps(langchain_data))

        # Preserve TTL if it existed
        ttl = redis_client.ttl(key)
        if ttl > 0:
            redis_client.expire(key, ttl)
        else:
            redis_client.expire(key, 86400)  # 24 hours default

        logger.info(f"✅ Migrated {key}: {len(langchain_messages)} messages")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to migrate {key}: {e}")
        return False


def validate_migration(key: str) -> bool:
    """
    Validate that a migrated key is in correct LangChain format.
    """
    try:
        data_raw = redis_client.get(key)
        if not data_raw:
            return False

        data = json.loads(data_raw)

        # Check LangChain structure
        if "messages" not in data:
            logger.error(f"❌ {key}: Missing 'messages' key")
            return False

        if not isinstance(data["messages"], list):
            logger.error(f"❌ {key}: 'messages' is not a list")
            return False

        # Check each message format
        for msg in data["messages"]:
            if "type" not in msg or "data" not in msg:
                logger.error(f"❌ {key}: Invalid message format")
                return False

            if msg["type"] not in ["human", "ai"]:
                logger.error(f"❌ {key}: Invalid message type: {msg['type']}")
                return False

        logger.info(f"✅ Validation passed for {key}")
        return True

    except Exception as e:
        logger.error(f"❌ Validation failed for {key}: {e}")
        return False


# ============================================================================
# MAIN MIGRATION
# ============================================================================

def main():
    """
    Main migration function.
    """
    logger.info("=" * 80)
    logger.info("LANGCHAIN MIGRATION SCRIPT")
    logger.info("=" * 80)

    # Step 1: Create backup
    logger.info("\n📦 Step 1: Creating backup...")
    backup_file = backup_redis_data()

    # Step 2: Find all chat history keys
    logger.info("\n🔍 Step 2: Finding chat history keys...")
    chat_keys = find_chat_history_keys()

    if not chat_keys:
        logger.info("ℹ️ No chat history keys found. Nothing to migrate.")
        return

    # Step 3: Migrate each key
    logger.info(f"\n🔄 Step 3: Migrating {len(chat_keys)} keys...")
    migrated_count = 0
    failed_count = 0

    for key in chat_keys:
        if migrate_chat_history(key):
            migrated_count += 1
        else:
            failed_count += 1

    # Step 4: Validate migrations
    logger.info(f"\n✅ Step 4: Validating migrations...")
    validation_passed = 0
    validation_failed = 0

    for key in chat_keys:
        if validate_migration(key):
            validation_passed += 1
        else:
            validation_failed += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"📊 Total keys found: {len(chat_keys)}")
    logger.info(f"✅ Successfully migrated: {migrated_count}")
    logger.info(f"❌ Failed migrations: {failed_count}")
    logger.info(f"✅ Validation passed: {validation_passed}")
    logger.info(f"❌ Validation failed: {validation_failed}")
    logger.info(f"📦 Backup saved to: {backup_file}")

    if validation_failed > 0:
        logger.warning("\n⚠️ Some validations failed! Check logs above.")
        logger.warning(f"⚠️ You can restore from backup: {backup_file}")
    else:
        logger.info("\n🎉 Migration completed successfully!")
        logger.info("🚀 You can now use LangChain-based HRMS extractor.")


def rollback_from_backup(backup_file: str):
    """
    Rollback migration using backup file.

    Usage:
        python migrate_to_langchain.py rollback redis_backup_20250110_123456.json
    """
    logger.info(f"🔄 Rolling back from {backup_file}...")

    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        restored_count = 0
        for key, data in backup_data.items():
            redis_client.set(key, data["value"])
            if data["ttl"] > 0:
                redis_client.expire(key, data["ttl"])
            restored_count += 1

        logger.info(f"✅ Restored {restored_count} keys from backup")

    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        if len(sys.argv) < 3:
            logger.error("❌ Usage: python migrate_to_langchain.py rollback <backup_file>")
            sys.exit(1)
        rollback_from_backup(sys.argv[2])
    else:
        main()
