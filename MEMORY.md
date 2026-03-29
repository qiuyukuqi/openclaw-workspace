# MEMORY.md - 长期记忆

---

## 🛡️ 铁律（Iron Rules）

### Rule 6 — 双层记忆存储（铁律）

Every pitfall/lesson learned → IMMEDIATELY store **TWO** memories to LanceDB before moving on:

- **Technical layer**: `Pitfall: [symptom]. Cause: [root cause]. Fix: [solution]. Prevention: [how to avoid]` (category: fact, importance ≥ 0.8)
- **Principle layer**: `Decision principle ([tag]): [behavioral rule]. Trigger: [when it applies]. Action: [what to do]` (category: decision, importance ≥ 0.85)
- After each store, **immediately `memory_recall`** with anchor keywords to verify retrieval. If not found, rewrite and re-store.
- Missing either layer = incomplete. Do NOT proceed to next topic until both are stored and verified.
- Also update relevant SKILL.md files to prevent recurrence.

### Rule 7 — LanceDB 卫生

Entries must be short and atomic (< 500 chars). Never store raw conversation summaries, large blobs, or duplicates. Prefer structured format with keywords for retrieval.

### Rule 8 — Recall before retry

On ANY tool failure, repeated error, or unexpected behavior, ALWAYS `memory_recall` with relevant keywords (error message, tool name, symptom) BEFORE retrying. LanceDB likely already has the fix. Blind retries waste time and repeat known mistakes.

### Rule 10 — 编辑前确认目标代码库

When working on memory plugins, confirm you are editing the intended package (e.g., `memory-lancedb-pro` vs built-in `memory-lancedb`) before making changes; use `memory_recall` + filesystem search to avoid patching the wrong repo.

### Rule 20 — 插件代码变更必须清 jiti 缓存（MANDATORY）

After modifying ANY `.ts` file under `plugins/`, MUST run `rm -rf /tmp/jiti/` BEFORE `openclaw gateway restart`. jiti caches compiled TS; restart alone loads STALE code. This has caused silent bugs multiple times. Config-only changes do NOT need cache clearing.

### Rule 21 — 记忆数据库健康防护（MANDATORY）

LanceDB 表可能因升级/重启损坏（Tables 为空但 .lance 文件存在）。已部署自动防护：
- **健康检查**：每小时 `~/.openclaw/workspace/scripts/memory-healthcheck.sh` 检测表状态
- **自动恢复**：检测到空表时自动从 `~/.openclaw/memory/backups/` 最新备份恢复
- **频繁备份**：每 6 小时 `~/.openclaw/workspace/scripts/memory-backup.sh` 创建快照
- **诊断命令**：`node --import jiti/register -e "import{connect}from'@lancedb/lancedb';connect(...).then(...)"`

---

## 📝 其他记忆

_(待补充)_
