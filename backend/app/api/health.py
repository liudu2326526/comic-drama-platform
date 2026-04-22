from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.deps import get_db
from app.infra.redis_client import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    res = {"db": "ok", "redis": "skipped"}
    try:
        redis = get_redis()
        await redis.ping()
        res["redis"] = "ok"
    except Exception:
        pass
    return ok(res)


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return ok({"ready": True})
