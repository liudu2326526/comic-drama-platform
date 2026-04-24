# coding:utf-8
import datetime
import hashlib
import hmac
import json
import time
from urllib.parse import quote
import requests

# ===========================================================================
# 基础配置信息
# ===========================================================================
SERVICE = "ark"
REGION = "cn-beijing"
HOST = "ark.cn-beijing.volcengineapi.com"
CONTENT_TYPE = "application/json"
PATH = "/"
VERSION = "2024-01-01"          # 必须定义

# 请求的凭证，从IAM或者STS服务中获取
AK = ""
SK = ""

# 轮询配置
POLL_INTERVAL = 3          # 秒
POLL_TIMEOUT = 120         # 秒

def norm_query(params: dict) -> str:
    """
    规范化查询参数（Query String）。
    将字典类型的参数按照 key 的字典序排序，并进行 URL 编码。
    
    :param params: 查询参数字典
    :return: 规范化后的查询字符串
    """
    query = ""
    for key in sorted(params.keys()):
        if isinstance(params[key], list):
            for k in params[key]:
                query += quote(key, safe="-_.~") + "=" + quote(str(k), safe="-_.~") + "&"
        else:
            query += quote(key, safe="-_.~") + "=" + quote(str(params[key]), safe="-_.~") + "&"
    return query[:-1].replace("+", "%20")

def hmac_sha256(key: bytes, content: str) -> bytes:
    """
    使用 HMAC-SHA256 算法生成签名。
    
    :param key: 签名的密钥
    :param content: 待签名的内容
    :return: 签名后的字节流
    """
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

def hash_sha256(content: str) -> str:
    """
    使用 SHA256 算法计算内容的哈希值。
    
    :param content: 待哈希的内容
    :return: 哈希后的十六进制字符串
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def request_api(method: str, date: datetime.datetime, query: dict, header: dict,
                ak: str, sk: str, body: str = "",
                action: str = None, version: str = None) -> requests.Response:
    """
    封装对 OpenAPI 的签名计算和请求调用过程。
    
    :param method: HTTP 请求方法，如 "GET", "POST"
    :param date: 请求发起的时间 (UTC 时间)
    :param query: URL 查询参数字典
    :param header: HTTP 请求头字典
    :param ak: Access Key ID
    :param sk: Secret Access Key
    :param body: HTTP 请求体 (默认为空字符串)
    :param action: API 操作名称，如果不提供则使用全局 ACTION
    :param version: API 版本，如果不提供则使用全局 VERSION
    :return: requests.Response 响应对象
    """
    # 使用传入的 action 和 version，否则使用全局变量
    final_action = action if action is not None else ACTION
    final_version = version if version is not None else VERSION

    # 1. 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": SERVICE,
        "region": REGION,
    }
    
    # 2. 初始化请求结构体
    # 合并基础 query 参数 (Action, Version) 和用户传入的 query 参数
    final_query = {"Action": final_action, "Version": final_version}
    if query:
        final_query.update(query)
        
    request_param = {
        "body": body if body else "",
        "host": HOST,
        "path": PATH,
        "method": method.upper(),
        "content_type": CONTENT_TYPE,
        "date": date,
        "query": final_query,
    }

    # 3. 准备签名的基础信息
    x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])
    
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }
    
    signed_headers_str = ";".join(["content-type", "host", "x-content-sha256", "x-date"])
    
    # 4. 构造规范化请求串 (CanonicalRequest)
    canonical_request_str = "\n".join([
        request_param["method"],
        request_param["path"],
        norm_query(request_param["query"]),
        "\n".join([
            "content-type:" + request_param["content_type"],
            "host:" + request_param["host"],
            "x-content-sha256:" + x_content_sha256,
            "x-date:" + x_date,
        ]),
        "",
        signed_headers_str,
        x_content_sha256,
    ])
    
    hashed_canonical_request = hash_sha256(canonical_request_str)
    credential_scope = "/".join([short_x_date, credential["region"], credential["service"], "request"])
    
    # 5. 构造待签名字符串 (StringToSign)
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])
    
    # 6. 计算签名 (Signature)
    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    # 7. 组装最终的 Authorization 请求头
    sign_result["Authorization"] = "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
        credential["access_key_id"] + "/" + credential_scope,
        signed_headers_str,
        signature,
    )
    
    # 8. 发起 HTTP 请求
    final_headers = header.copy() if header else {}
    final_headers.update(sign_result)
    
    response = requests.request(
        method=request_param["method"],
        url="https://{}{}".format(request_param["host"], request_param["path"]),
        headers=final_headers,
        params=request_param["query"],
        data=request_param["body"]
    )
    return response

def extract_nested_value(data, *keys):
    """
    从嵌套字典中安全提取字符串值。
    
    :param data: 原始响应数据（字典）
    :param keys: 多级键名路径
    :return: 提取的字符串，如果不存在则返回空字符串
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return ""
        else:
            return ""
    if isinstance(current, str):
        return current
    elif current is not None:
        return str(current)
    return ""

def get_asset_status(asset_id: str):
    """
    调用 GetAsset 接口查询资产状态。
    返回 (status, url, err_msg, resp_json)
    """
    body = json.dumps({"Id": asset_id})
    current_date = datetime.datetime.utcnow()
    response = request_api(
        method="POST",
        date=current_date,
        query={},
        header={},
        ak=AK,
        sk=SK,
        body=body,
        action="GetAsset",
        version=VERSION
    )
    if response.status_code != 200:
        return "", "", f"HTTP {response.status_code}: {response.text}", None
    
    try:
        resp_json = response.json()
    except json.JSONDecodeError:
        return "", "", f"Invalid JSON response: {response.text}", None
    
    # 不再在这里打印 JSON，返回给调用者
    status = extract_nested_value(resp_json, "Result", "Status")
    if not status:
        status = extract_nested_value(resp_json, "Status")
    
    url = extract_nested_value(resp_json, "Result", "URL")
    if not url:
        url = extract_nested_value(resp_json, "URL")
    
    err_msg = extract_nested_value(resp_json, "Result", "Error")
    if not err_msg:
        err_msg = extract_nested_value(resp_json, "Error")
    
    return status, url, err_msg, resp_json

def wait_for_asset_active(asset_id: str):
    """
    轮询 GetAsset 直到资产状态变为 Active，或超时/失败。
    返回 (success, final_url_or_error)
    """
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status, url, err_msg, resp_json = get_asset_status(asset_id)
        # 先打印状态
        print(f"Asset status: {status}")
        # 再打印完整的 JSON 响应
        if resp_json is not None:
            print("GetAsset response:")
            print(json.dumps(resp_json, indent=2, ensure_ascii=False))
        else:
            print("GetAsset response: (none)")
        
        if status == "Active":
            if url:
                return True, url
            else:
                return False, f"Asset is Active but URL is empty (asset_id={asset_id})"
        elif status == "Failed":
            return False, f"Asset processing failed: {err_msg or 'unknown error'}"
        elif status == "Processing":
            time.sleep(POLL_INTERVAL)
            continue
        else:
            # 未知状态，保守地继续轮询
            print(f"Unexpected status '{status}', continue polling...")
            time.sleep(POLL_INTERVAL)
    
    return False, f"Polling timeout after {POLL_TIMEOUT} seconds, asset_id={asset_id}"

def main():
    """
    主程序执行入口，演示创建资产并轮询至活跃状态。
    """
    # 准备请求体参数（示例，请根据实际情况修改）
    data = {
        "GroupId": "group-2026xxxxxxx",
        "URL": "https://ark-project.tos-cn-beijing.volces.com/doc_image/i2v_foxrgirl.png",
        "AssetType": "Image",
    }
    data_json = json.dumps(data)
    
    current_date = datetime.datetime.utcnow()
    
    print(f"==================================================")
    print(f"正在发起 CreateAsset 请求...")
    print(f"请求体: {data_json}")
    print(f"==================================================")
    
    # 调用创建资产接口
    response = request_api(
        method="POST",
        date=current_date,
        query={},
        header={},
        ak=AK,
        sk=SK,
        body=data_json,
        action="CreateAsset",
        version=VERSION
    )
    
    if response.status_code != 200:
        print(f"CreateAsset failed: HTTP {response.status_code}\n{response.text}")
        return
    
    try:
        resp_json = response.json()
    except json.JSONDecodeError:
        print(f"Invalid JSON response from CreateAsset: {response.text}")
        return
    
    print("CreateAsset response:")
    print(json.dumps(resp_json, indent=4, ensure_ascii=False))
    
    # 提取 AssetId（兼容不同返回结构）
    asset_id = extract_nested_value(resp_json, "Result", "Id")
    if not asset_id:
        asset_id = extract_nested_value(resp_json, "Result", "AssetId")
    if not asset_id:
        asset_id = extract_nested_value(resp_json, "Id")
    if not asset_id:
        asset_id = extract_nested_value(resp_json, "AssetId")
    
    if not asset_id:
        print("Cannot find AssetId in CreateAsset response.")
        return
    
    print(f"Asset created, AssetId = {asset_id}")
    
    # 轮询等待资产变为 Active
    success, result = wait_for_asset_active(asset_id)
    if success:
        print("Asset is active.")
    else:
        print(f"Polling failed: {result}")

if __name__ == '__main__':
    main()