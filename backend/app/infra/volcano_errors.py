from __future__ import annotations
import json
import httpx


class VolcanoError(Exception):
    """基类。所有从 volcano_client / volcano_asset_client 抛出的业务可识别异常都继承此类。"""
    retryable = False


class VolcanoAuthError(VolcanoError):
    retryable = False


class VolcanoParamError(VolcanoError):
    retryable = False


class VolcanoContentFilterError(VolcanoError):
    retryable = False


class VolcanoRateLimitError(VolcanoError):
    retryable = True
    def __init__(self, msg: str, retry_after: int | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


class VolcanoServerError(VolcanoError):
    retryable = True


class VolcanoTimeoutError(VolcanoError):
    retryable = True


_CONTENT_FILTER_CODES = {
    "ContentFilter", "OutputImageSensitiveContentDetected",
    "OutputVideoSensitiveContentDetected", "content_filter",
}
_INPUT_IMAGE_FILTER_PREFIXES = (
    "InputImageSensitiveContentDetected",
    "InputSensitiveContentDetected",
)


def is_content_filter_code(code: str) -> bool:
    return bool(
        code
        and (
            code in _CONTENT_FILTER_CODES
            or any(code.startswith(prefix) for prefix in _INPUT_IMAGE_FILTER_PREFIXES)
        )
    )


def humanize_volcano_error_message(message: str) -> str:
    if any(message.startswith(prefix) for prefix in _INPUT_IMAGE_FILTER_PREFIXES):
        return "参考图被平台判定含隐私或敏感信息，请更换参考图后重试"
    if is_content_filter_code(message):
        return "输入内容触发平台安全策略，请调整文案或参考图后重试"
    return message


def classify_http(resp: httpx.Response) -> None:
    """2xx 不抛;4xx/5xx 按类别抛对应 VolcanoError 子类。"""
    if 200 <= resp.status_code < 300:
        return
    code_str = _extract_error_code(resp)
    if resp.status_code in (401, 403):
        raise VolcanoAuthError(f"auth {resp.status_code}: {code_str}")
    if resp.status_code == 429:
        ra = resp.headers.get("Retry-After")
        raise VolcanoRateLimitError("rate limited", int(ra) if ra and ra.isdigit() else None)
    if resp.status_code == 400:
        if is_content_filter_code(code_str):
            raise VolcanoContentFilterError(humanize_volcano_error_message(code_str))
        raise VolcanoParamError(f"{code_str or resp.text[:200]}")
    if 500 <= resp.status_code < 600:
        raise VolcanoServerError(f"{resp.status_code}: {resp.text[:200]}")
    raise VolcanoError(f"unexpected http {resp.status_code}: {resp.text[:200]}")


def _extract_error_code(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        err = data.get("error") or {}
        if isinstance(err, dict):
            return str(err.get("code", ""))
    return ""


def classify_exception(e: Exception) -> VolcanoError:
    """将 httpx 异常映射为 VolcanoError 子类"""
    if isinstance(
        e, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.PoolTimeout)
    ):
        return VolcanoTimeoutError(str(e))
    if isinstance(e, httpx.TransportError):
        return VolcanoServerError(str(e))
    if isinstance(e, VolcanoError):
        return e
    return VolcanoServerError(f"Unexpected error: {e}")
