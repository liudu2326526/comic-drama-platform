import json
from app.infra.volcano_asset_client import (
    build_canonical_request, sign,
)

def test_signature_matches_official_demo():
    """使用官方 demo(docs/huoshan_api/人像库 demo/CreateAssetGroup_Demo (1).py)跑出的
    固定样本回归。任何签名算法改动都会被这条测试卡住。"""
    ak = "AKLTDEMO"
    sk = "SECDEMO"
    host = "ark.cn-beijing.volcengineapi.com"
    region = "cn-beijing"
    service = "ark"
    date = "20260421T120000Z"
    body = json.dumps({"Name": "demo", "GroupType": "AIGC",
                       "ProjectName": "default"}, separators=(",", ":"))
    query = "Action=CreateAssetGroup&Version=2024-01-01"
    expected_authorization = (
        "HMAC-SHA256 Credential=AKLTDEMO/20260421/cn-beijing/ark/request, "
        "SignedHeaders=content-type;host;x-content-sha256;x-date, "
        "Signature=84ccf7dcb4332c72bd124824adaefa8f0410e8f1b78acbc779f7c8cf451128d6"
    )
    authz = sign(
        access_key=ak, secret_key=sk, host=host, region=region,
        service=service, x_date=date, method="POST", path="/", query=query,
        body=body.encode("utf-8"),
    )
    assert authz == expected_authorization

def test_canonical_request_sorts_query_by_key():
    # Version 在前(字典序)→ 签名输入里也要是排序后的
    cr = build_canonical_request(
        method="POST", path="/",
        query="Action=CreateAssetGroup&Version=2024-01-01",
        headers={"content-type": "application/json",
                 "host": "ark.cn-beijing.volcengineapi.com",
                 "x-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                 "x-date": "20260421T120000Z"},
        body_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    # Query 被按 key 字典序重排:Action → Version
    assert "Action=CreateAssetGroup&Version=2024-01-01" in cr
