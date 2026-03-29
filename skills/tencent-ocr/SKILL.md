---
name: tencent-ocr
description: 腾讯云文字识别（OCR）服务，用于从图片中提取文字内容。当用户要求识别图片文字、提取图片中的文字、图片转文字、OCR识别时使用此技能。支持本地图片和网络图片，支持通用文字识别（高精度/快速）、手写文字识别等多种模式。
---

# 腾讯云 OCR 文字识别

从图片中识别并提取文字内容，基于腾讯云 OCR API。

## 环境配置

需要设置以下环境变量（通过 OpenClaw 配置或系统环境变量）：

```bash
export TENCENT_SECRET_ID="你的SecretId"
export TENCENT_SECRET_KEY="你的SecretKey"
```

## 使用方式

调用 `scripts/ocr.py` 脚本：

```bash
python scripts/ocr.py <图片路径或URL> [类型]
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| 图片路径 | 本地文件路径或 HTTP/HTTPS URL |
| 类型 | 可选，默认 `general` |

**支持的 OCR 类型：**

| 类型 | 说明 | API |
|------|------|-----|
| `general` | 通用文字识别（高精度） | GeneralAccurateOCR |
| `accurate` | 通用文字识别（高精度） | GeneralAccurateOCR |
| `fast` | 通用文字识别（快速） | GeneralBasicOCR |
| `basic` | 通用文字识别（基础） | GeneralBasicOCR |
| `handwriting` | 手写文字识别 | HandwritingOCR |

## 使用示例

**识别本地图片：**
```bash
python scripts/ocr.py /path/to/image.png
```

**识别网络图片：**
```bash
python scripts/ocr.py https://example.com/image.jpg
```

**使用快速模式：**
```bash
python scripts/ocr.py /path/to/image.png fast
```

**识别手写文字：**
```bash
python scripts/ocr.py /path/to/handwriting.png handwriting
```

## 输出格式

脚本输出识别到的文字内容，每行一个文字块。错误信息输出到 stderr。

## 注意事项

- 图片大小限制：Base64 编码后不超过 7MB
- 支持格式：PNG、JPG、JPEG、BMP、GIF
- API 区域：ap-beijing
- 请求超时：30 秒
