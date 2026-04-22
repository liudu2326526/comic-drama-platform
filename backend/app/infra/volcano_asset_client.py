import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.infra.volcano_errors import (
    classify_http, 
    classify_exception, 
    VolcanoError, 
    VolcanoTimeoutError
)


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_canonical_request(method, path, query, headers, body_sha256) -> str:
    # query:按 key 字典序排序 + URL encode(RFC3986)
    items = sorted(
        (kv.split("=", 1) if "=" in kv else (kv, ""))
        for kv in query.split("&") if kv
    )
    canonical_query = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in items
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = "".join(
        f"{h}:{headers[h]}\n" for h in ("content-type", "host",
                                        "x-content-sha256", "x-date")
    )
    return "\n".join([method, path, canonical_query, canonical_headers,
                      signed_headers, body_sha256])


def calc_signature(secret_key, date_short, region, service, string_to_sign) -> str:
    k_date = _hmac(secret_key.encode("utf-8"), date_short)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "request")
    return hmac.new(k_signing, string_to_sign.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def sign(*, access_key, secret_key, host, region, service, x_date,
         method, path, query, body) -> str:
    body_sha = _sha256_hex(body)
    headers = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": body_sha,
        "x-date": x_date,
    }
    canonical = build_canonical_request(method, path, query, headers, body_sha)
    canonical_sha = _sha256_hex(canonical.encode("utf-8"))
    date_short = x_date[:8]   # YYYYMMDD
    credential_scope = f"{date_short}/{region}/{service}/request"
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, canonical_sha])
    signature = calc_signature(secret_key, date_short, region, service, string_to_sign)
    signed_headers = "content-type;host;x-content-sha256;x-date"
    return (f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")


class VolcanoAssetClient:
    def __init__(self):
        s = get_settings()
        if not s.volc_access_key_id or not s.volc_secret_access_key:
            raise VolcanoError("人像库 AK/SK 未配置")
        self._s = s
        self._client = httpx.AsyncClient(
            base_url=f"https://{s.volc_asset_host}",
            timeout=30.0,
            trust_env=False,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _now_x_date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    async def _call(self, action: str, body: dict) -> dict:
        b = json.dumps(body, separators=(",", ":")).encode("utf-8")
        x_date = self._now_x_date()
        query = f"Action={action}&Version={self._s.volc_asset_api_version}"
        authz = sign(
            access_key=self._s.volc_access_key_id,
            secret_key=self._s.volc_secret_access_key,
            host=self._s.volc_asset_host,
            region=self._s.volc_asset_region,
            service=self._s.volc_asset_service,
            x_date=x_date, method="POST", path="/", query=query, body=b,
        )
        headers = {
            "Authorization": authz,
            "Content-Type": "application/json",
            "Host": self._s.volc_asset_host,
            "X-Date": x_date,
            "X-Content-Sha256": _sha256_hex(b),
        }
        try:
            resp = await self._client.post(f"/?{query}", content=b, headers=headers)
        except httpx.HTTPError as e:
            raise classify_exception(e)
        classify_http(resp)
        return resp.json().get("Result") or resp.json()

    async def create_asset_group(self, name, description=None):
        return await self._call("CreateAssetGroup", {
            "Name": name, "Description": description or "",
            "GroupType": "AIGC", "ProjectName": self._s.ark_project_name,
        })

    async def create_asset(self, group_id, url, asset_type="Image", name=""):
        return await self._call("CreateAsset", {
            "GroupId": group_id, "URL": url, "AssetType": asset_type,
            "Name": name, "ProjectName": self._s.ark_project_name,
        })

    async def get_asset(self, asset_id):
        return await self._call("GetAsset", {
            "Id": asset_id, "ProjectName": self._s.ark_project_name,
        })

    async def wait_asset_active(self, asset_id, *, timeout=None, interval=None) -> dict:
        """轮询直到 Status=Active;Failed 则抛 VolcanoError;超时抛 VolcanoTimeoutError。"""
        import asyncio
        t = timeout or self._s.asset_wait_timeout_sec
        iv = interval or self._s.asset_wait_interval_sec
        start = time.monotonic()
        while time.monotonic() - start < t:
            info = await self.get_asset(asset_id)
            st = info.get("Status")
            if st == "Active":
                return info
            if st == "Failed":
                raise VolcanoError(f"asset {asset_id} failed")
            await asyncio.sleep(iv)
        raise VolcanoTimeoutError(f"asset {asset_id} not active in {t}s")
