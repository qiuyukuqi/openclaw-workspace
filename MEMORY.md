# MEMORY.md - 长期记忆

> 结构化记忆模板，参考Claude Code Session Memory系统设计
> 最后更新：2026-04-07

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

### Rule 22 — 如实报告结果（源自Claude Code）

如果测试失败，如实说明失败输出。如果你没有运行验证步骤，就如实说而不是暗示成功了。永远不要声称\"所有测试通过\"，除非你真的运行了并且看到了通过结果。

---

## 📍 当前状态（Current State）

_正在做什么？下一步是什么？每次对话结束前必须更新。_

最近在做的：
- auto-publisher全平台发布流水线（公众号+头条+小红书）
- GitHub仓库备份和清理
- Claude Code源码学习→能力改造（2026-04-07）

待办：
- [ ] full_pipeline.py实际运行测试（已跑通一次，待再次验证）
- [ ] 小红书cookie定期刷新
- [ ] 头条cookie定期从Windows导出
- [ ] Phase 2技能开发（/simplify、/stuck、Magic Docs）

---

## 🔧 常用工作流（Workflow）

_常用命令、脚本、操作顺序。_

### GitHub推送
```bash
cd /root/.openclaw/workspace
git add -A && git commit -m "描述" && git push origin master
```
remote已配置token，无需认证。

### 全平台发布流水线
```bash
python3 /root/.openclaw/workspace/skills/auto-publisher/full_pipeline.py --auto
```
10步全自动：选题→调研→写作→润色→配图→生图→排版→公众号→改编→分发
- 从指定步骤开始：`--step adapt`
- Cookie来源：Windows服务器43.135.179.141

### 定时任务恢复
```bash
cat ~/.openclaw/workspace/crontab.conf | crontab -
```

### 邮件监控
```bash
cd ~/.openclaw/workspace && python3 skills/email-monitor/scripts/check_mail.py --once
```

### 记忆维护
- LanceDB查询：memory_recall工具
- 文件记忆：memory/YYYY-MM-DD.md + MEMORY.md

---

## 🐛 错误与修复（Errors & Fixes）

_遇到的错误和修复方法。避免重复踩坑。_

### 公众号标题截断
- **问题**：公众号API标题限制22个GBK字节，AI混入英文导致超限截断
- **修复**：Writer/Polish prompt加强"纯中文"约束，截断逻辑增加安全余量
- **时间**：2026-04-07

### 小红书 page.url bug
- **问题**：`page.url` 应为 `self.page.url`
- **修复**：platforms/xiaohongshu.py 中修正
- **时间**：2026-04-07

### 头条号 save参数含义反转
- **问题**：save=0是保存草稿，save=1是发布/提交审核
- **修复**：路由拦截将无pgc_id的save=0改为save=1
- **时间**：2026-04-06

### jti缓存导致插件修改不生效
- **问题**：修改plugins/下的.ts文件后，restart加载旧代码
- **修复**：`rm -rf /tmp/jiti/` 再 restart
- **时间**：2026-03起反复出现

### 知乎反自动化检测
- **问题**：cookie注入后被重定向到account/unhuman安全验证页
- **状态**：无法绕过，放弃知乎发布

---

## 📂 关键项目（Key Projects）

| 项目 | 路径 | 说明 |
|------|------|------|
| OpenClaw Workspace | `/root/.openclaw/workspace/` | 主工作目录 |
| auto-publisher | `skills/auto-publisher/` | 全平台发布流水线 |
| wechat-publisher | `skills/wechat-publisher/` | 公众号写作发布 |
| email-monitor | `skills/email-monitor/` | 邮箱监控+新闻简报 |
| shift-reminder | `skills/shift-reminder/` | 倒班提醒 |
| GitHub仓库 | `qiuyukuqi/openclaw-workspace` | 工作空间备份 |

---

## 🎯 关键结果（Key Results）

_用户要求的特定输出，精确记录。_

- 成功发布的头条文章URLs: 7625653364616888859, 7625656767678136842, 7625686755395633674
- full_pipeline.py首次试跑成功：哪吒GT文章，7分钟完成10步全流程
- GitHub仓库已清理推送（移除957个垃圾文件：浏览器缓存、封面图片、pyc）

---

## 📚 通用知识（General Knowledge）

_学到的通用技巧、最佳实践。_

### Claude Code源码学习精华（2026-04-07）
- **Session Memory结构化模板**：固定section+token限制（单section≤2000，总计≤12000）
- **四层上下文压缩**：Snip→MicroCompact→ContextCollapse→AutoCompact
- **AutoDream记忆整合**：4阶段（Orient→Gather→Consolidate→Prune），24h+5session触发
- **边际递减检测**：连续3轮增量<500 token就停，比单纯token计数聪明
- **Feature Gate**：编译期死代码消除，未启用功能零运行时成本
- **Fork子代理模式**：git worktree隔离+AsyncLocalStorage+邮箱通信
- **缓存编辑**：直接操作API缓存层而非重建上下文（ant-only高级特性）
- **Prompt技巧**：`<analysis>`草稿区、few-shot、针对模型版本的防御性指令

### 编程最佳实践（源自Claude Code）
- 不要为一次性操作创建抽象，三行相似代码好过早过早抽象
- 默认不写注释，只在WHY不显而易见时才加
- 行内手动字符串处理/路径拼接/类型判断应优先找已有utility
- 循环/事件处理器中的状态更新需加变更检测守卫避免no-op通知

---

_记忆模板版本：v2.0（2026-04-07升级）_
