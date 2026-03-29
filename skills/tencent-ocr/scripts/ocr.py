#!/usr/bin/env python3
"""
腾讯云文字识别（OCR）工具
使用腾讯云 OCR API 识别图片中的文字

环境变量:
    TENCENT_SECRET_ID: 腾讯云 SecretId
    TENCENT_SECRET_KEY: 腾讯云 SecretKey

用法:
    python ocr.py <image_path_or_url> [--type general|accurate|fast]
"""

import os
import sys
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from urllib.parse import quote
import urllib.request
import urllib.parse

# 腾讯云 OCR API 配置
SERVICE = "ocr"
HOST = "ocr.ap-beijing.tencentcloudapi.com"
ENDPOINT = "https://ocr.ap-beijing.tencentcloudapi.com"
REGION = "ap-beijing"
VERSION = "2018-11-19"

# OCR 类型映射
OCR_ACTIONS = {
    "general": "GeneralAccurateOCR",      # 通用文字识别（高精度）
    "accurate": "GeneralAccurateOCR",     # 通用文字识别（高精度）
    "fast": "GeneralBasicOCR",            # 通用文字识别（快速）
    "basic": "GeneralBasicOCR",           # 通用文字识别（基础）
    "handwriting": "HandwritingOCR",      # 手写文字识别
    "web": "WebOCR",                      # 网页元素识别
}


def get_credentials():
    """从环境变量或 .env 文件获取腾讯云凭证"""
    secret_id = os.environ.get("TENCENT_SECRET_ID")
    secret_key = os.environ.get("TENCENT_SECRET_KEY")
    
    # 如果环境变量未设置，尝试从 .env.tencent 文件读取
    if not secret_id or not secret_key:
        # 查找 .env.tencent 文件
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env.tencent"),
            os.path.expanduser("~/.openclaw/workspace/.env.tencent"),
            os.path.join(os.getcwd(), ".env.tencent"),
        ]
        
        for env_path in possible_paths:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("TENCENT_SECRET_ID="):
                                secret_id = line.split("=", 1)[1]
                            elif line.startswith("TENCENT_SECRET_KEY="):
                                secret_key = line.split("=", 1)[1]
                    if secret_id and secret_key:
                        break
                except Exception:
                    pass
    
    if not secret_id or not secret_key:
        print("错误: 请设置环境变量 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY", file=sys.stderr)
        print("或创建 .env.tencent 文件", file=sys.stderr)
        sys.exit(1)
    
    return secret_id, secret_key


def sha256_hash(data):
    """计算 SHA256 哈希"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key, data):
    """计算 HMAC-SHA256"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(key, str):
        key = key.encode("utf-8")
    return hmac.new(key, data, hashlib.sha256).digest()


def sign(secret_key, date, service, string_to_sign):
    """生成签名"""
    date_key = hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    service_key = hmac_sha256(date_key, service)
    signing_key = hmac_sha256(service_key, "tc3_request")
    signature = hmac_sha256(signing_key, string_to_sign)
    return signature.hex()


def make_request(action, params, secret_id, secret_key):
    """发送 API 请求"""
    # 时间戳
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    
    # 请求体
    body = json.dumps(params)
    
    # 构建规范请求串
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json; charset=utf-8"
    canonical_headers = "content-type:%s\nhost:%s\n" % (ct, HOST)
    signed_headers = "content-type;host"
    hashed_request_payload = sha256_hash(body)
    canonical_request = "%s\n%s\n%s\n%s\n%s\n%s" % (
        http_request_method, canonical_uri, canonical_querystring,
        canonical_headers, signed_headers, hashed_request_payload
    )
    
    # 构建待签名字符串
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = "%s/%s/tc3_request" % (date, SERVICE)
    hashed_canonical_request = sha256_hash(canonical_request)
    string_to_sign = "%s\n%s\n%s\n%s" % (
        algorithm, timestamp, credential_scope, hashed_canonical_request
    )
    
    # 计算签名
    signature = sign(secret_key, date, SERVICE, string_to_sign)
    
    # 构建 Authorization
    authorization = "%s Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        algorithm, secret_id, credential_scope, signed_headers, signature
    )
    
    # 发送请求
    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VERSION,
        "X-TC-Region": REGION,
    }
    
    req = urllib.request.Request(ENDPOINT, data=body.encode("utf-8"), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP 错误 {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def image_to_base64(image_path):
    """将图片转换为 Base64"""
    # 检查是否为 URL
    if image_path.startswith("http://") or image_path.startswith("https://"):
        try:
            with urllib.request.urlopen(image_path, timeout=30) as response:
                image_data = response.read()
                return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            print(f"下载图片失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 本地文件
        if not os.path.exists(image_path):
            print(f"错误: 文件不存在 - {image_path}", file=sys.stderr)
            sys.exit(1)
        
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


def extract_text(response):
    """从 API 响应中提取文字"""
    if "Response" not in response:
        return None, response
    
    resp = response["Response"]
    
    if "Error" in resp:
        return None, resp["Error"]
    
    # 提取文字
    texts = []
    if "TextDetections" in resp:
        for item in resp["TextDetections"]:
            if "DetectedText" in item:
                texts.append(item["DetectedText"])
    
    return "\n".join(texts), None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n支持的 OCR 类型:")
        for t, action in OCR_ACTIONS.items():
            print(f"  {t}: {action}")
        sys.exit(1)
    
    image_path = sys.argv[1]
    ocr_type = sys.argv[2] if len(sys.argv) > 2 else "general"
    
    if ocr_type not in OCR_ACTIONS:
        print(f"错误: 不支持的 OCR 类型 '{ocr_type}'", file=sys.stderr)
        print(f"支持的类型: {', '.join(OCR_ACTIONS.keys())}", file=sys.stderr)
        sys.exit(1)
    
    # 获取凭证
    secret_id, secret_key = get_credentials()
    
    # 读取图片
    print(f"正在处理图片: {image_path}", file=sys.stderr)
    image_base64 = image_to_base64(image_path)
    
    # 调用 API
    action = OCR_ACTIONS[ocr_type]
    params = {"ImageBase64": image_base64}
    
    print(f"调用 {action}...", file=sys.stderr)
    response = make_request(action, params, secret_id, secret_key)
    
    # 提取文字
    text, error = extract_text(response)
    
    if error:
        print(f"识别失败: {json.dumps(error, ensure_ascii=False, indent=2)}", file=sys.stderr)
        sys.exit(1)
    
    # 输出结果
    print(text)


if __name__ == "__main__":
    main()
