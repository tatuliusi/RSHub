from fastapi import APIRouter
from qdrant_client import QdrantClient
import redis as redis_lib

from src.config import get_settings

router = APIRouter()


@router.get("/health")
async def health():
    settings = get_settings()
    checks = {}

    # Qdrant
    try:
        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    # Redis
    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
