from obs import ObsClient

from app.config import get_settings


def _get_obs_client():
    s = get_settings()
    return ObsClient(
        access_key_id=s.obs_ak,
        secret_access_key=s.obs_sk,
        server=s.obs_endpoint,
    )


def upload_file_to_obs(local_path: str, object_key: str) -> dict:
    s = get_settings()
    if s.obs_mock:
        # OBS_MOCK 只允许在非 real 模式下使用
        if s.ai_provider_mode == "real":
            raise RuntimeError("OBS_MOCK=1 不得在 AI_PROVIDER_MODE=real 下使用,必须配置真实 OBS")
        return {"success": True, "object_key": object_key, "url": get_obs_url(object_key)}
    if not all([s.obs_ak, s.obs_sk, s.obs_endpoint, s.obs_bucket, s.obs_public_base_url]):
        raise RuntimeError("OBS 配置不完整")
    client = _get_obs_client()
    try:
        resp = client.putFile(s.obs_bucket, object_key, file_path=local_path)
        if resp.status < 300:
            return {"success": True, "object_key": object_key, "url": get_obs_url(object_key)}
        raise RuntimeError(f"OBS upload failed: {resp.errorCode}: {resp.errorMessage}")
    finally:
        client.close()


def get_obs_url(object_key: str) -> str:
    s = get_settings()
    if not s.obs_public_base_url:
        if s.obs_mock:
            # mock 模式允许 fallback
            return f"https://obs-mock.local/{object_key.lstrip('/')}"
        raise RuntimeError("OBS_PUBLIC_BASE_URL 未配置")
    base = s.obs_public_base_url.rstrip("/")
    return f"{base}/{object_key.lstrip('/')}"
