from datetime import datetime, timezone
from pathlib import Path
import asyncio

import httpx

from app.config import get_settings
from app.infra import obs_store
from app.infra.ulid import new_id
from app.infra.volcano_errors import classify_http, classify_exception

ALLOWED_KINDS = {
    "character",
    "scene",
    "shot",
    "character_style_reference",
    "scene_style_reference",
    "character_full_body",
    "character_headshot",
}


async def persist_generated_asset(*, url: str, project_id: str, kind: str,
                                  ext: str = "png") -> str:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"kind must be one of {ALLOWED_KINDS}, got {kind!r}")
    s = get_settings()
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    object_key = f"projects/{project_id}/{kind}/{day}/{new_id()}.{ext}"
    abs_path = Path(s.storage_root) / "tmp" / object_key
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 下载火山临时 URL 到本地
        async with httpx.AsyncClient(timeout=s.asset_download_timeout) as client:
            async with client.stream("GET", url) as resp:
                classify_http(resp)
                with open(abs_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(s.asset_download_chunk):
                        f.write(chunk)
        
        # 使用 asyncio.to_thread 避免阻塞事件循环
        await asyncio.to_thread(obs_store.upload_file_to_obs, str(abs_path), object_key)
        
        return object_key
    except httpx.HTTPError as e:
        raise classify_exception(e)
    finally:
        # 清理临时文件
        if abs_path.exists():
            abs_path.unlink()


def build_asset_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    return obs_store.get_obs_url(object_key)
