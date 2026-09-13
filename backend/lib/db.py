"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "status_checks": [IndexModel([("timestamp", DESCENDING)], name="timestamp_desc")],
    "scans": [
        IndexModel([("id", ASCENDING)], name="scan_id", unique=True),
        IndexModel([("scanned_at", DESCENDING)], name="scanned_at_desc"),
        IndexModel([("status", ASCENDING)], name="status"),
        IndexModel([("region", ASCENDING)], name="region"),
        IndexModel([("owner_id", ASCENDING), ("scanned_at", DESCENDING)], name="owner_scanned"),
    ],
    "inspection_images": [
        IndexModel([("id", ASCENDING)], name="image_id", unique=True),
        IndexModel([("inspection_id", ASCENDING)], name="inspection_id"),
        IndexModel([("owner_id", ASCENDING), ("inspection_id", ASCENDING)], name="image_owner_inspection"),
    ],
    "users": [
        IndexModel([("id", ASCENDING)], name="user_id", unique=True),
        IndexModel([("email", ASCENDING)], name="user_email", unique=True),
    ],
    "sessions": [
        IndexModel([("token_hash", ASCENDING)], name="session_token", unique=True),
        IndexModel([("expires_at", ASCENDING)], name="session_expiry", expireAfterSeconds=0),
    ],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)
