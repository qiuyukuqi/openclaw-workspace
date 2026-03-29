---
name: knowledge-base
description: 个人知识库RAG系统。支持上传文件（PDF、Word、TXT、Markdown）、自动向量化存储、智能检索回答。触发词：上传文件、存入知识库、从知识库查找、知识库搜索、检索文档、查找资料、文档问答。使用场景：(1) 用户上传文件要求存储 (2) 用户提问需要从已上传的文档中检索答案 (3) 用户要求查看/管理已上传的文档。
---

# 个人知识库 RAG 系统

## 功能概览

| 功能 | 命令 | 说明 |
|------|------|------|
| 📤 上传文件 | `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py add <文件路径>` | 自动分块、向量化、存储 |
| 🔍 检索查询 | `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py search "<问题>"` | 返回相关内容+来源 |
| 📋 查看列表 | `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py list` | 列出所有已上传文档 |
| 🗑️ 删除文档 | `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py delete <文档ID>` | 删除指定文档 |
| 📊 查看状态 | `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py status` | 查看知识库统计信息 |

## 配置信息

| 项目 | 值 |
|------|-----|
| 存储路径 | `~/.openclaw/workspace/skills/knowledge-base/data/` |
| 向量数据库 | Chroma（本地持久化） |
| 嵌入模型 | paraphrase-multilingual-MiniLM-L12-v2（本地运行） |
| 脚本路径 | `~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py` |

## 使用流程

### 1️⃣ 用户上传文件

当用户发送文件时：

1. 使用 `feishu_im_bot_image` 下载文件到 `/tmp/openclaw/`
2. 调用 `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py add <文件路径>` 存入知识库
3. 告知用户存储结果（文档ID、分块数）

### 2️⃣ 用户提问

当用户提问涉及已上传文档内容时：

1. 调用 `python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py search "<问题>"`
2. 基于检索结果回答，标注来源引用
3. 如果不确定，明确说明

### 3️⃣ 管理文档

- **查看列表**：`python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py list`
- **删除文档**：`python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py delete <doc_id>`
- **查看状态**：`python3 ~/.openclaw/workspace/skills/knowledge-base/scripts/kb_manager.py status`

## 支持的文件格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| PDF | .pdf | 自动提取文本 |
| Word | .docx, .doc | 自动提取文本 |
| 文本 | .txt, .md | 直接读取 |
| 表格 | .csv | 按行处理 |
| 代码 | .py, .js, .json 等 | 直接读取 |

## 分块策略

| 参数 | 值 | 说明 |
|------|-----|------|
| chunk_size | 1000 | 每块1000字符 |
| chunk_overlap | 200 | 块之间重叠200字符 |
| separators | ["\n\n", "\n", ". ", " ", ""] | 分层分割 |

## 检索参数

| 参数 | 值 | 说明 |
|------|-----|------|
| top_k | 5 | 返回最相关的5个片段 |
| score_threshold | 0.5 | 相似度阈值 |

## 回答格式

回答时应包含：

1. **直接回答**：基于检索内容的答案
2. **来源引用**：标注 `[来源: 文档名]`
3. **置信度**：如果不确定，明确说明

示例：
```
根据您上传的《产品手册.pdf》，该功能的使用方法是...

[来源: 产品手册.pdf 第3章]

如果需要更详细的信息，可以查看原文档相关章节。
```

## 注意事项

1. **首次使用**：需要安装依赖 `pip install chromadb langchain langchain-openai langchain-community pypdf python-docx`
2. **文件大小**：建议单个文件不超过10MB
3. **定期清理**：定期删除不需要的文档，保持知识库整洁
4. **隐私安全**：知识库存储在本地，不会上传到云端

## 依赖安装

```bash
pip install --break-system-packages chromadb langchain langchain-community langchain-text-splitters sentence-transformers pypdf python-docx
```

**注意**：首次使用会自动下载嵌入模型（约400MB），后续使用本地缓存。
