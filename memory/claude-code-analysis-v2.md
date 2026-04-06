# Claude Code 源码深度分析报告 v2

> 分析时间：2026-04-07 | 源码路径：/tmp/claude-code-study/src
> 本轮重点：上一轮遗漏的核心模块深度剖析

---

## 1. AutoDream — 自动记忆整合系统

**文件：** `services/autoDream/` (4个文件)

### 1.1 核心机制

AutoDream 是 Claude Code 的**后台记忆整合引擎**，自动将积累的会话记忆提炼为持久化知识。它以 forked subagent 方式运行，完全不影响主会话。

**执行流程（4层门控，成本从低到高）：**

```
1. 时间门：距上次整合 >= 24小时（一次 stat 调用）
2. 会话门：自上次整合后有 >= 5 个会话被修改（扫描 transcript mtime）
3. 锁门：无其他进程正在整合（PID 锁文件）
4. 记忆目录门：autoMemory 必须启用
```

**关键代码（autoDream.ts）：**

```typescript
const DEFAULTS: AutoDreamConfig = {
  minHours: 24,    // 最小间隔24小时
  minSessions: 5,  // 最少5个会话
}

// 从 GrowthBook 动态配置获取阈值
function getConfig(): AutoDreamConfig {
  const raw = getFeatureValue_CACHED_MAY_BE_STALE<Partial<AutoDreamConfig> | null>(
    'tengu_onyx_plover', null,
  )
  // 防御性验证每个字段...
}

// 每轮 REPL 的入口（per-turn 成本：一次 GB 缓存读取 + 一次 stat）
export async function executeAutoDream(context, appendSystemMessage): Promise<void> {
  await runner?.(context, appendSystemMessage)
}
```

### 1.2 整合提示词（4阶段）

**consolidationPrompt.ts** 定义了结构化的4阶段整合流程：

| 阶段 | 名称 | 动作 |
|------|------|------|
| Phase 1 | Orient | ls 记忆目录，读取 MEMORY.md 索引，扫描已有主题文件 |
| Phase 2 | Gather | 读取日志（logs/YYYY/MM/YYYY-MM-DD.md），检查旧记忆是否过时，按需 grep transcript |
| Phase 3 | Consolidate | 合并新信号到已有文件（而非创建重复），转换相对日期为绝对日期，删除矛盾事实 |
| Phase 4 | Prune & Index | 更新 MEMORY.md 索引（<200行 & <25KB），移除过时条目，精简超长条目 |

### 1.3 并发锁机制

**consolidationLock.ts** — 使用文件 mtime 作为 lastConsolidatedAt 时间戳：

```typescript
const LOCK_FILE = '.consolidate-lock'
const HOLDER_STALE_MS = 60 * 60 * 1000  // 1小时过期

// 锁文件 = PID 内容 + mtime 时间戳
// 死锁恢复：PID 不存活时自动回收
// 失败回滚：rollbackConsolidationLock() 将 mtime 回退到获取前的值
```

### 1.4 KAIROS 模式下的差异

```typescript
function isGateOpen(): boolean {
  if (getKairosActive()) return false  // KAIROS 模式使用 disk-skill dream
  if (getIsRemoteMode()) return false
  if (!isAutoMemoryEnabled()) return false
  return isAutoDreamEnabled()
}
```

KAIROS（Assistant 模式）使用不同的记忆写入策略：**每日日志追加**而非实时 MEMORY.md 更新。 nightly /dream 再将日志提炼为主题文件。

---

## 2. Memory Dir System — 文件记忆系统

**文件：** `memdir/memdir.ts`, `memdir/paths.ts`, `memdir/memoryTypes.ts`

### 2.1 目录结构

```
~/.claude/
  projects/<sanitized-git-root>/
    memory/
      MEMORY.md          ← 入口索引（<200行，<25KB）
      user_role.md       ← 主题文件（frontmatter 格式）
      feedback_testing.md
      logs/
        2026/
          04/
            2026-04-07.md  ← KAIROS 每日日志
      team/               ← TEAMMEM 共享记忆（feature gate）
```

### 2.2 记忆类型体系（4类）

```typescript
// memoryTypes.ts 定义了4种记忆类型
TYPES_SECTION_INDIVIDUAL  // Individual 模式的类型说明
WHAT_NOT_TO_SAVE_SECTION  // 不应该保存什么
WHEN_TO_ACCESS_SECTION    // 何时读取记忆
TRUSTING_RECALL_SECTION   // 信任召回结果
```

记忆 frontmatter 格式：
```yaml
---
name: user_role
description: The user's role and responsibilities
type: user  # user | feedback | project | reference
---
```

### 2.3 路径解析优先级

```typescript
// paths.ts — 记忆目录路径解析链
1. CLAUDE_COWORK_MEMORY_PATH_OVERRIDE env var（Cowork 专用，完整路径覆盖）
2. settings.json autoMemoryDirectory（仅 policy/local/user 三个可信源，排除 projectSettings 防恶意仓库）
3. ~/.claude/projects/<sanitized-git-root>/memory/（默认）
```

### 2.4 MEMORY.md 截断策略

```typescript
export const MAX_ENTRYPOINT_LINES = 200
export const MAX_ENTRYPOINT_BYTES = 25_000  // ~125字符/行 × 200行 的 p97 防护

function truncateEntrypointContent(raw: string): EntrypointTruncation {
  // 先按行截断（自然边界），再按字节截断（防止超长行）
  // 截断时追加警告，指明是哪个上限触发
}
```

### 2.5 KAIROS vs 非 KAIROS 模式

| 特性 | 标准模式 | KAIROS 模式 |
|------|---------|-------------|
| 写入方式 | 实时写入主题文件 + MEMORY.md | 追加到每日日志 |
| 索引维护 | 主 agent 维护 | nightly /dream 提炼 |
| 整合方式 | AutoDream forked agent | disk-skill dream |
| 系统提示 | buildMemoryPrompt() | buildAssistantDailyLogPrompt() |

---

## 3. Context Budget 系统

### 3.1 Token Budget（feature: `TOKEN_BUDGET`）

**文件：** `query/tokenBudget.ts`

```typescript
const COMPLETION_THRESHOLD = 0.9     // 使用90%时继续
const DIMINISHING_THRESHOLD = 500    // 连续3轮增量 <500 token 视为边际递减

type TokenBudgetDecision = ContinueDecision | StopDecision

function checkTokenBudget(tracker, agentId, budget, globalTurnTokens) {
  // 如果是 subagent → 不适用 budget
  if (agentId || budget === null) return { action: 'stop' }

  const pct = (turnTokens / budget) * 100
  const isDiminishing = tracker.continuationCount >= 3 && delta < 500

  // 未达90%且未边际递减 → 继续（附带进度消息）
  // 达到边际递减或已超过 → 停止
}
```

**触发点：**
- `query.ts:280` — 每轮查询前创建 BudgetTracker
- `query.ts:1308` — 每轮查询后检查是否应继续
- `screens/REPL.tsx` — UI 层显示 budget 进度
- `utils/attachments.ts` — 附件预算分配

### 3.2 Compact Token Budget

**文件：** `services/compact/compact.ts`

```typescript
export const POST_COMPACT_TOKEN_BUDGET = 50_000          // compact 后恢复的 token 预算
export const POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000    // 每个文件最大 token
export const POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000   // 技能预算
export const POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000   // 每个技能最大 token
```

### 3.3 Auto Compact 系统

**文件：** `services/compact/autoCompact.ts`

```typescript
export const AUTOCOMPACT_BUFFER_TOKENS = 13_000   // 自动 compact 缓冲区
export const MANUAL_COMPACT_BUFFER_TOKENS = 3_000  // 手动 compact 缓冲区

// 阈值 = contextWindow - 13000 token
// 支持 CLAUDE_AUTOCOMPACT_PCT_OVERRIDE 环境变量覆盖
// 连续失败3次后停止尝试
```

### 3.4 Compaction 系统

**compact.ts** 是核心压缩引擎：
- 支持 partial compact（定向压缩）和 full compact
- compact 前剥离图片（减少 API 调用本身超长）
- compact 后按 token budget 恢复最近访问的文件和技能
- 支持 prompt cache sharing（相同前缀的会话共享 compact 缓存）

---

## 4. ULTRAPLAN — 云端深度规划系统

**文件：** `utils/ultraplan/` (2个文件)

### 4.1 核心概念

ULTRAPLAN 是一个**远程规划模式**——将用户的复杂需求 teleport 到云端（CCR 远程会话），由 Opus 模型生成详细执行计划，用户在浏览器中审批后回传执行。

### 4.2 工作流

```
用户输入包含 "ultraplan" 关键词
    ↓
keyword.ts 检测触发（智能跳过引号/路径/斜杠命令中的误触发）
    ↓
teleport 到 CCR 远程会话（Plan Mode）
    ↓
远程 Claude 生成计划 → 调用 ExitPlanMode 工具
    ↓
用户在浏览器中审批/拒绝/编辑计划
    ↓
ccrSession.ts 轮询等待结果（3秒间隔，30分钟超时）
    ↓
结果回传：approved（远程执行）/ teleport（本地执行）/ rejected
```

### 4.3 关键字检测（keyword.ts）

```typescript
// 智能关键词检测，跳过：
// - 引号内：`ultraplan`, "ultraplan", <ultraplan> 等
// - 路径：src/ultraplan/foo.ts
// - 文件扩展名：ultraplan.tsx
// - 问句：ultraplan?（关于功能的提问不触发）
// - 斜杠命令：/rename ultraplan（已经是斜杠命令了）

// 还支持 "ultrareview" 关键词触发
```

### 4.4 审批状态机（ExitPlanModeScanner）

```typescript
// 纯状态分类器，无 I/O，可单元测试
class ExitPlanModeScanner {
  // 状态转换：
  // running → (无 ExitPlanMode) → needs_input
  // needs_input → (用户在浏览器回复) → running
  // running → (ExitPlanMode 发出，无结果) → plan_ready
  // plan_ready → (被拒绝) → running
  // plan_ready → (被批准) → 轮询结束

  // 优先级：approved > terminated > rejected > pending > unchanged
}
```

---

## 5. Feature Flags 完整清单（89个）

所有 feature flag 通过 `feature('FLAG_NAME')` 调用，基于 Bun 的 tree-shaking 实现编译时分支消除。

### 5.1 🟢 已发布/活跃使用的 Flags

| Flag | 功能描述 |
|------|---------|
| `KAIROS` | Assistant 持久化模式（daemon 化的长期会话） |
| `KAIROS_CHANNELS` | 渠道通知支持（Slack/Discord 等） |
| `KAIROS_GITHUB_WEBHOOKS` | GitHub Webhook 触发 |
| `KAIROS_BRIEF` | 简报模式 |
| `KAIROS_DREAM` | KAIROS 专用 dream 技能 |
| `KAIROS_PUSH_NOTIFICATION` | 推送通知 |
| `PROACTIVE` | 主动模式（与 KAIROS 互为替代） |
| `DAEMON` | Daemon 进程模式（`claude daemon` / `claude --daemon-worker`） |
| `BRIDGE_MODE` | 桥接模式（WebSocket 连接 VS Code/IDE） |
| `AGENT_TRIGGERS` | 定时任务调度器（cron scheduler） |
| `COORDINATOR_MODE` | 协调器模式（多 agent 编排） |
| `EXTRACT_MEMORIES` | 后台记忆提取（每轮对话后 fork subagent 提取） |
| `TOKEN_BUDGET` | Token 预算追踪（+500k auto-continue） |
| `ULTRAPLAN` | 云端深度规划 |
| `ULTRATHINK` | 深度思考模式 |
| `FORK_SUBAGENT` | Subagent fork 机制 |
| `CONTEXT_COLLAPSE` | 上下文折叠 |
| `REACTIVE_COMPACT` | 响应式压缩（而非定时） |
| `HISTORY_SNIP` | 历史会话摘要 |
| `TEAMMEM` | 团队共享记忆 |
| `SESSION_MEMORY` | 会话记忆 |
| `TRANSCRIPT_CLASSIFIER` | 会话记录自动分类 |
| `COMMIT_ATTRIBUTION` | Git 提交归因追踪 |
| `FILE_PERSISTENCE` | 文件持久化追踪 |
| `MCP_SKILLS` | MCP 技能系统 |
| `MCP_RICH_OUTPUT` | MCP 富输出 |
| `CHICAGO_MCP` | MCP 芝加哥版本 |
| `UDS_INBOX` | UDS 消息收件箱 |
| `VOICE_MODE` | 语音模式 |
| `WEB_BROWSER_TOOL` | 内置浏览器工具 |
| `VERIFICATION_AGENT` | 验证 Agent |
| `WORKFLOW_SCRIPTS` | 工作流脚本 |
| `SKILL_IMPROVEMENT` | 技能自改进 |
| `LODESTONE` | 磁石功能（用途待确认） |
| `TORCH` | Torch 功能 |
| `TERMINAL_PANEL` | 终端面板（IDE 集成） |
| `BG_SESSIONS` | 后台会话 |
| `CCR_MIRROR` | CCR 镜像 |
| `CCR_AUTO_CONNECT` | CCR 自动连接 |
| `CCR_REMOTE_SETUP` | CCR 远程设置 |
| `DIRECT_CONNECT` | 直连模式 |
| `SSH_REMOTE` | SSH 远程连接 |
| `CLAUDE_APPS` | Claude 应用构建 |
| `TEMPLATES` | 模板系统 |
| `MONITOR_TOOL` | 监控工具 |
| `BUDDY` | Buddy 协作模式 |
| `DOWNLOAD_USER_SETTINGS` | 设置云端下载 |
| `UPLOAD_USER_SETTINGS` | 设置云端上传 |
| `SETTINGS_SYNC` | 设置同步 |
| `OVERFLOW_TEST_TOOL` | 溢出测试工具 |
| `BREAK_CACHE_COMMAND` | 缓存中断命令 |
| `DUMP_SYSTEM_PROMPT` | 导出系统提示 |
| `STREAMLINED_OUTPUT` | 精简输出模式 |
| `MESSAGE_ACTIONS` | 消息操作（引用/编辑等） |
| `NATIVE_CLIENT_ATTESTATION` | 原生客户端认证 |
| `NATIVE_CLIPBOARD_IMAGE` | 原生剪贴板图片 |
| `QUICK_SEARCH` | 快速搜索 |
| `HISTORY_PICKER` | 历史选择器 |
| `CONNECTOR_TEXT` | 连接器文本 |
| `BASH_CLASSIFIER` | Bash 命令分类器 |
| `SELF_HOSTED_RUNNER` | 自托管 Runner |
| `RUN_SKILL_GENERATOR` | 技能生成器 |
| `UNATTENDED_RETRY` | 无人值守重试 |
| `SLOW_OPERATION_LOGGING` | 慢操作日志 |

### 5.2 🟡 内部/灰度测试 Flags

| Flag | 功能描述 |
|------|---------|
| `ABLATION_BASELINE` | 消融实验基线 |
| `AGENT_MEMORY_SNAPSHOT` | Agent 记忆快照 |
| `CACHED_MICROCOMPACT` | 缓存微压缩 |
| `COWORKER_TYPE_TELEMETRY` | 协作者类型遥测 |
| `ANTI_DISTILLATION_CC` | 反蒸馏保护 |
| `TREE_SITTER_BASH` | Tree-sitter Bash 解析 |
| `TREE_SITTER_BASH_SHADOW` | Tree-sitter 影子模式（对比测试） |
| `POWERSHELL_AUTO_MODE` | PowerShell 自动模式 |
| `PROMPT_CACHE_BREAK_DETECTION` | Prompt Cache 中断检测 |
| `PERFETTO_TRACING` | 性能追踪 |
| `COMPACTION_REMINDERS` | 压缩提醒 |
| `AWAY_SUMMARY` | 离开摘要 |
| `AUTO_THEME` | 自动主题 |
| `NEW_INIT` | 新初始化流程 |
| `REVIEW_ARTIFACT` | 审查制品 |
| `HARD_FAIL` | 硬失败模式 |
| `HOOK_PROMPTS` | Hook 提示 |
| `EXPERIMENTAL_SKILL_SEARCH` | 实验性技能搜索 |
| `IS_LIBC_GLIBC` / `IS_LIBC_MUSL` | libc 检测（构建时） |
| `BUILTIN_EXPLORE_PLAN_AGENTS` | 内置探索计划 Agent |
| `AGENT_TRIGGERS_REMOTE` | 远程定时任务 |
| `BYOC_ENVIRONMENT_RUNNER` | 自建环境 Runner |

### 5.3 🔵 GrowthBook 远程配置实验

除了编译时 feature flag，还有通过 GrowthBook SDK 的远程实验配置：

| 实验键 | 用途 |
|--------|------|
| `tengu_onyx_plover` | AutoDream 配置（minHours, minSessions, enabled） |
| `tengu_passport_quail` | Extract Memories 开关 |
| `tengu_slate_thimble` | 非交互会话的 Extract Memories |
| `tengu_coral_fern` | 记忆搜索历史上下文功能 |
| `tengu_moth_copse` | 跳过 MEMORY.md 索引步骤 |
| `tengu_herring_clock` | 团队记忆开关 |
| `tengu_amber_*` | 多个功能实验（flint, prism, stoat, wren, stork 等） |
| `tengu_cobalt_*` | 多个功能实验（frost, harbor, lantern, raccoon） |
| `tengu_slate_heron` | Session Memory 配置 |
| `tengu_sage_compass` | 功能实验 |
| `tengu_quartz_lantern` | 功能实验 |
| `tengu_pebble_leaf_prune` | 功能实验 |
| `tengu_marble_*` | fox, sandcastle 功能实验 |

---

## 6. KAIROS — 自主 Daemon 模式

### 6.1 核心定位

KAIROS 是 Claude Code 从"用户驱动工具"进化为**自主助手**的核心特性。与传统 REPL 会话不同，KAIROS 模式下会话是**长期持久化的**。

### 6.2 与标准模式的关键差异

**AppStateStore.ts 中的 KAIROS 状态：**
```typescript
interface AppState {
  kairosEnabled: boolean  // KAIROS 模式是否激活
  // workflows（工作流）运行在 REMOTE daemon 子进程中
}
```

**feature() 调用分布（print.ts 为主）：**
```typescript
// PROACTIVE 和 KAIROS 互为替代，共用大量代码路径
feature('PROACTIVE') || feature('KAIROS')
```

### 6.3 记忆系统差异

标准模式：主 agent 实时写 MEMORY.md + 主题文件
KAIROS 模式：
- **追加写入**每日日志 `logs/YYYY/MM/YYYY-MM-DD.md`
- 不直接编辑 MEMORY.md
- **nightly /dream** 技能将日志提炼为主题文件 + MEMORY.md
- 凌晨跨天时，通过 `date_change` 附件通知 agent 切换到新日志文件

```typescript
// memdir.ts — KAIROS 模式的记忆提示
function buildAssistantDailyLogPrompt(skipIndex = false): string {
  // "This session is long-lived. As you work, record anything worth remembering
  //  by appending to today's daily log file."
  // "Do not rewrite or reorganize the log — it is append-only."
}
```

### 6.4 触发场景（从 feature 调用推断）

| 子功能 | Flag |
|--------|------|
| 简报推送 | `KAIROS_BRIEF` |
| 渠道通知（Slack/Discord） | `KAIROS_CHANNELS` |
| GitHub Webhook 触发 | `KAIROS_GITHUB_WEBHOOKS` |
| 定时任务（cron） | `KAIROS` + `AGENT_TRIGGERS` |
| Dream 记忆整合 | `KAIROS_DREAM` |
| 推送通知 | `KAIROS_PUSH_NOTIFICATION` |

---

## 7. DAEMON 模式

**文件：** `entrypoints/cli.tsx`

```typescript
// Daemon worker 模式
if (feature('DAEMON') && args[0] === '--daemon-worker') {
  // 作为守护进程 worker 启动
}

// Daemon 主命令
if (feature('DAEMON') && args[0] === 'daemon') {
  // 启动 daemon 主进程
}

// Daemon 需要 Bridge 模式
feature('DAEMON') && feature('BRIDGE_MODE')
```

Daemon 模式允许 Claude Code 作为**后台服务运行**，通过 WebSocket Bridge 与 IDE 通信。`--daemon-worker` 标志用于启动实际的工作进程，`daemon` 命令启动管理进程。

---

## 8. Extract Memories — 实时记忆提取

**文件：** `services/extractMemories/extractMemories.ts`, `services/extractMemories/prompts.ts`

### 8.1 与 AutoDream 的关系

| 特性 | Extract Memories | AutoDream |
|------|-----------------|-----------|
| 触发时机 | 每轮对话结束后 | 每24小时 + 5个会话 |
| 运行方式 | forked subagent | forked subagent |
| 功能 | 补充主 agent 遗漏的记忆 | 整合+提炼所有记忆 |
| 工具权限 | 仅读+写记忆目录 | 仅读+写记忆目录（Bash 限只读） |

### 8.2 开关链

```typescript
// paths.ts
export function isExtractModeActive(): boolean {
  // 1. GrowthBook tengu_passport_quail（功能开关）
  if (!getFeatureValue_CACHED_MAY_BE_STALE('tengu_passport_quail', false))
    return false
  // 2. 非交互会话需要额外的 tengu_slate_thimble 开关
  return !getIsNonInteractiveSession() ||
    getFeatureValue_CACHED_MAY_BE_STALE('tengu_slate_thimble', false)
}

// print.ts — 主 REPL 中的调用
if (feature('EXTRACT_MEMORIES') && isExtractModeActive()) {
  // 执行提取
}
```

---

## 9. 关键发现与洞察

### 9.1 架构模式

1. **Feature Flag 双层体系**：编译时 `feature()` 实现零成本 tree-shaking + 运行时 GrowthBook 远程配置实现灰度发布
2. **Forked Agent 模式**：AutoDream、Extract Memories、Ultraplan 都通过 `runForkedAgent()` 运行独立 agent，不影响主会话
3. **渐进式记忆架构**：短期（会话内）→ 每日日志（KAIROS）→ AutoDream 提炼 → MEMORY.md 持久索引
4. **状态机模式**：Ultraplan 的 ExitPlanModeScanner 是纯函数状态机，可离线回放测试

### 9.2 遥测体系

`tengu_` 前缀的事件超过 **500个**，覆盖了几乎每个功能点的成功/失败/性能指标。这是极其细粒度的产品遥测。

### 9.3 对 OpenClaw 的启示

1. **Memory Dir 模式**值得参考：文件即记忆，MEMORY.md 索引 + 主题文件分离
2. **AutoDream 整合策略**：4阶段结构化整合比随机保存有效得多
3. **Token Budget 追踪**：边际递减检测（连续3轮增量 <500 token）是优雅的停止策略
4. **Ultraplan 规划模式**：复杂任务先规划再执行，支持用户审批和本地/远程执行选择

---

*报告生成时间：2026-04-07 01:36 CST*
