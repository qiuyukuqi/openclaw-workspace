# Errors Log

Command failures, exceptions, and unexpected behaviors.

---

## 2026-03-17

### LanceDB Tables 为空
- **Error**: `db.tableNames()` 返回 `[]`，2470 个 .lance 文件存在但无法访问
- **Context**: 用户反馈记忆丢失
- **Resolution**: 从备份恢复，部署自动健康检查

### RAG 知识库依赖缺失
- **Error**: `ModuleNotFoundError: No module named 'chromadb'`
- **Cause**: venv 虚拟环境不完整，缺少 pip
- **Resolution**: 重建 venv，手动安装 get-pip.py，重装所有依赖

---
