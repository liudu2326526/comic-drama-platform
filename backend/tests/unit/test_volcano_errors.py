import httpx
import pytest

from app.infra.volcano_errors import (
    VolcanoAuthError, VolcanoParamError,
    VolcanoRateLimitError, VolcanoContentFilterError,
    VolcanoServerError, classify_http,
)


def _resp(status, body=b"{}"):
    return httpx.Response(status_code=status, content=body,
                          request=httpx.Request("GET", "http://x"))


class TestClassify:
    def test_401_auth(self):
        with pytest.raises(VolcanoAuthError):
            classify_http(_resp(401))

    def test_403_auth(self):
        with pytest.raises(VolcanoAuthError):
            classify_http(_resp(403))

    def test_429_ratelimit_preserves_retry_after(self):
        r = httpx.Response(429, headers={"Retry-After": "12"}, content=b"{}",
                           request=httpx.Request("GET", "http://x"))
        with pytest.raises(VolcanoRateLimitError) as exc:
            classify_http(r)
        assert exc.value.retry_after == 12

    def test_400_param(self):
        with pytest.raises(VolcanoParamError):
            classify_http(_resp(400, b'{"error":{"code":"InvalidParameter"}}'))

    def test_content_filter_from_400_code(self):
        r = _resp(400, b'{"error":{"code":"ContentFilter"}}')
        with pytest.raises(VolcanoContentFilterError):
            classify_http(r)

    def test_input_image_privacy_filter_from_400_code_uses_friendly_message(self):
        r = _resp(400, b'{"error":{"code":"InputImageSensitiveContentDetected.PrivacyInformation"}}')
        with pytest.raises(
            VolcanoContentFilterError,
            match="参考图被平台判定含隐私或敏感信息，请更换参考图后重试",
        ):
            classify_http(r)

    def test_5xx_server(self):
        with pytest.raises(VolcanoServerError):
            classify_http(_resp(502))

    def test_2xx_ok_no_raise(self):
        # 不抛
        classify_http(_resp(200))
