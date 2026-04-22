# coding:utf-8
import datetime
import hashlib
import hmac
import json
from urllib.parse import quote
import requests

# ===========================================================================
# 基础配置信息
# ===========================================================================
# 以下参数视服务不同而不同，一个服务内通常是一致的，不同接口注意修改action
SERVICE = "ark"
ACTION = "CreateAssetGroup"
VERSION = "2024-01-01"
REGION = "cn-beijing"
HOST = "ark.cn-beijing.volcengineapi.com"
CONTENT_TYPE = "application/json"
PATH = "/"

# 请求的凭证，从IAM或者STS服务中获取
AK = ""
SK = ""

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

def request_api(method: str, date: datetime.datetime, query: dict, header: dict, ak: str, sk: str, body: str = "") -> requests.Response:
    """
    封装对 OpenAPI 的签名计算和请求调用过程。
    
    :param method: HTTP 请求方法，如 "GET", "POST"
    :param date: 请求发起的时间 (UTC 时间)
    :param query: URL 查询参数字典
    :param header: HTTP 请求头字典
    :param ak: Access Key ID
    :param sk: Secret Access Key
    :param body: HTTP 请求体 (默认为空字符串)
    :return: requests.Response 响应对象
    """
    # 1. 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": SERVICE,
        "region": REGION,
    }
    
    # 2. 初始化请求结构体
    # 合并基础 query 参数 (Action, Version) 和用户传入的 query 参数
    final_query = {"Action": ACTION, "Version": VERSION}
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
    # 使用 header.copy() 避免污染外部传入的字典
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


def main():
    """
    主程序执行入口，用于演示创建 Asset Group 的 API 调用。
    """
    # 准备请求体参数
    data = {
        "Name": "test-group",
        "Description": "test",
        "GroupType": "AIGC",
    }
    data_json = json.dumps(data)
    
    # 获取当前 UTC 时间
    current_date = datetime.datetime.utcnow()
    
    print(f"==================================================")
    print(f"正在发起请求: Action={ACTION}, Version={VERSION}")
    print(f"请求体: {data_json}")
    print(f"==================================================")
    
    # 调用封装好的请求函数
    response = request_api(
        method="POST", 
        date=current_date, 
        query={}, 
        header={}, 
        ak=AK, 
        sk=SK, 
        body=data_json
    )
    
    # 打印响应结果
    print(f"响应状态码: {response.status_code}")
    try:
        # 尝试格式化输出 JSON 响应内容
        parsed_response = response.json()
        print("响应内容:")
        print(json.dumps(parsed_response, indent=4, ensure_ascii=False))
    except json.JSONDecodeError:
        print(f"响应内容:\n{response.text}")

if __name__ == '__main__':
    main()
