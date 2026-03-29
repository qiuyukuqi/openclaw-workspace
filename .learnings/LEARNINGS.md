# Learnings Log

Captured learnings, corrections, and discoveries. Review before major tasks.

---

## 2026-03-17

### LanceDB 表丢失问题
- **Category**: pitfall
- **Symptom**: `memory_recall` 返回空，但 `.lance` 文件存在
- **Cause**: 数据库表结构丢失（`db.tableNames()` 返回 `[]`），可能是重启或升级导致
- **Fix**: 从 `~/.openclaw/memory/backups/` 最新备份恢复
- **Prevention**: 已部署每小时健康检查脚本 `memory-healthcheck.sh` 自动检测并恢复

### RAG 知识库 venv 损坏
- **Category**: pitfall
- **Symptom**: venv/bin/pip 不存在
- **Cause**: venv 创建不完整
- **Fix**: 使用 `python3 -m venv --without-pip` 然后手动安装 get-pip.py

### 操作后清理垃圾文件
- **Category**: best_practice
- **Rule**: 修复、升级、安装依赖后必须检查垃圾文件
- **Common junk**: `/tmp/*.py`、`~/.cache/pip`、npm 缓存
- **Action**: 清理 pip 缓存用 `pip cache purge`

---
