from pathlib import Path
import pytest
import respx
import httpx

from app.infra.asset_store import build_asset_url, persist_generated_asset

@respx.mock
@pytest.mark.asyncio
async def test_downloads_uploads_obs_and_returns_object_key(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("OBS_AK", "ak")
    monkeypatch.setenv("OBS_SK", "sk")
    monkeypatch.setenv("OBS_ENDPOINT", "obs.cn-south-1.myhuaweicloud.com")
    monkeypatch.setenv("OBS_BUCKET", "bucket")
    monkeypatch.setenv("OBS_PUBLIC_BASE_URL", "https://static.example.com")
    from app.config import get_settings
    get_settings.cache_clear()

    uploaded = {}
    def fake_upload(local_path: str, object_key: str):
        uploaded["object_key"] = object_key
        uploaded["bytes"] = Path(local_path).read_bytes()
        return {"success": True, "object_key": object_key,
                "url": f"https://static.example.com/{object_key}"}
    monkeypatch.setattr("app.infra.obs_store.upload_file_to_obs", fake_upload)

    respx.get("https://cdn/xxx.png").mock(
        return_value=httpx.Response(200, content=b"PNGDATA"))

    object_key = await persist_generated_asset(
        url="https://cdn/xxx.png",
        project_id="01HPROJ",
        kind="character",
        ext="png",
    )
    assert object_key.startswith("projects/01HPROJ/character/")
    assert object_key.endswith(".png")
    assert uploaded["object_key"] == object_key
    assert uploaded["bytes"] == b"PNGDATA"
    assert build_asset_url(object_key) == f"https://static.example.com/{object_key}"

@pytest.mark.asyncio
async def test_rejects_unknown_kind():
    with pytest.raises(ValueError):
        await persist_generated_asset(url="https://x", project_id="p",
                                      kind="something_else")
