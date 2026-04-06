# Claude Code 完整源码深度分析报告

> 基于 GitHub 泄露的 Claude Code 完整源码（~1902 文件，~512K 行代码）
> 分析时间：2026-04-07

---

## 一、整体架构概览

Claude Code 是 Anthropic 构建的 AI 编程助手，采用 **Bun** 运行时 + **React/Ink** 终端 UI，核心是一个异步生成器驱动的 **agentic query loop**。

### 架构分层

```
┌─────────────────────────────────────┐
│           CLI 入口 (main.tsx)        │
├─────────────────────────────────────┤
│         REPL (React/Ink 终端UI)      │
├─────────────────────────────────────┤
│     Query Loop (query.ts 核心)       │  ← 异步生成器，工具循环
├──────────┬──────────┬───────────────┤
│  Tools   │ Services │  Coordinator  │
│  20+工具  │ API/压缩  │  多Agent协调   │
├──────────┴──────────┴───────────────┤
│   Utils (权限/安全/Git/MCP/Swarm)   │
├─────────────────────────────────────┤
│   Hooks / Plugins / Skills / Tasks  │
└─────────────────────────────────────┘
```

### 技术栈
- **运行时**: Bun（非 Node.js），利用 `bun:bundle` 的 `feature()` 做编译期死代码消除
- **UI**: React + Ink（终端渲染）
- **API**: Anthropic SDK，支持 prompt caching（`cache_control`）、extended thinking、web search
- **类型**: Zod v4 schema 验证
- **传输**: MCP SDK（stdio/SSE/StreamableHTTP/WebSocket）

---

## 二、核心 Query Loop（src/query.ts）

这是整个系统的心脏。采用 **async generator** 模式实现 agentic 工具循环：

```typescript
async function* queryLoop(params: QueryParams, consumedCommandUuids: string[]) {
  let state: State = { messages, toolUseContext, ... }
  while (true) {
    // 1. Snip compact（行级裁剪）
    // 2. Micro compact（工具结果压缩）
    // 3. Context collapse（上下文折叠）
    // 4. Auto compact（完整摘要压缩）
    // 5. API 调用（流式）
    // 6. 工具执行（并行）
    // 7. 循环或终止
  }
}
```

### 关键设计

**Thinking 块处理规则**（源码注释非常有趣）：
> "The rules of thinking are lengthy and fortuitous. They require plenty of thinking of most long duration and deep meditation for a wizard to wrap one's noggin around."

1. 包含 thinking/redacted_thinking 的消息必须在 max_thinking_length > 0 的 query 中
2. thinking 块不能是最后一条消息
3. thinking 块必须在整个 assistant trajectory 中保持

**Max Output Tokens 恢复机制**：当输出被截断时（max_output_tokens），系统会自动重试，最多恢复 3 次，每次提升到 `ESCALATED_MAX_TOKENS = 64,000`。

**Token Budget 系统**：通过 `createBudgetTracker()` 跟踪每轮 token 消耗，支持自动续费（auto-continue）。

**Task Budget**：与 Claude API 的 `task_budget` beta 功能集成，跨 compact 边界跟踪总消耗。

### Continue 机制

循环有 7 个 continue site（继续点），通过不可变 state 对象传递：

```typescript
type Continue = { reason: string }
// 在工具执行后、compact后、重试后等位置 continue
state = { ...state, messages: newMessages, turnCount: state.turnCount + 1 }
```

---

## 三、工具系统（src/tools/）

### 3.1 工具构建框架（buildTool）

所有工具通过 `buildTool()` 统一构建，返回 `ToolDef<InputSchema, Output>` 类型：

```typescript
export const FileEditTool = buildTool({
  name: FILE_EDIT_TOOL_NAME,
  strict: true,
  maxResultSizeChars: 100_000,
  async description() { return 'A tool for editing files' },
  async prompt() { return getEditToolDescription() },
  checkPermissions(input, context): Promise<PermissionDecision>,
  renderToolUseMessage, renderToolResultMessage,
  // ...
})
```

### 3.2 BashTool（src/tools/BashTool/）

核心特性：
- **安全沙箱**: `bashSecurity.ts` 实现命令安全检查
- **后台运行**: 支持 background/pty 模式，`yieldMs` 控制后台等待
- **危险模式检测**: `isDangerousBashPermission()` 检查自动允许的危险规则
  - 工具级允许（Bash 无规则内容）→ 危险
  - `python:*`, `node:*`, `bash -c` → 危险
  - 通配符匹配解释器 → 危险

### 3.3 FileEditTool

- **精确文本替换**: `findActualString()` 查找实际匹配，`getPatchForEdit()` 生成 patch
- **引号风格保持**: `preserveQuoteStyle()` 保持原始引号风格
- **大小限制**: 最大 1GB 文件（`MAX_EDIT_FILE_SIZE = 1024 * 1024 * 1024`）
- **LSP 集成**: 编辑后通知 LSP 诊断清除、VSCode SDK MCP
- **Magic Doc 检测**: 检查团队记忆文件中的秘密泄露

### 3.4 WebSearchTool

使用 Anthropic 原生 `web_search_20250305` beta API：
- 最大 8 次搜索（`max_uses: 8`）
- 支持域名白名单/黑名单过滤
- 结果包含标题、URL 和模型生成的文本评论

### 3.5 MCPTool

代理 MCP 协议工具：
- `.passthrough()` schema 允许任意输入
- 在 `mcpClient.ts` 中动态覆盖 name/description/call
- 最大结果 100,000 字符

### 3.6 AgentTool（最复杂的工具，~800行）

**架构设计**：
- 支持同步/异步/远程/队友（teammate）四种执行模式
- **Fork 子代理**: 创建隔离的 git worktree，后台运行
- **多 Agent 协调**: `spawnMultiAgent()` 生成队友
- **进度追踪**: `ProgressTracker` 记录工具调用次数、token 消耗、最近活动

```typescript
type AgentToolInput = {
  description: string      // 3-5词任务描述
  prompt: string           // 任务指令
  subagent_type?: string   // 专业代理类型
  model?: 'sonnet' | 'opus' | 'haiku'
  run_in_background?: boolean
  name?: string            // 可寻址名称
  team_name?: string
  isolation?: 'worktree' | 'remote'
  cwd?: string
}
```

**后台任务自动化**：
- 超过 120 秒自动转为后台（`getAutoBackgroundMs()`）
- 进度报告通过 `AgentProgress` 类型传递

---

## 四、Prompt 工程（src/constants/prompts.ts）

### 4.1 System Prompt 架构

采用 **分段缓存** 策略：

```typescript
// 静态部分（全局缓存）| 动态边界 | 动态部分（会话特定）
export const SYSTEM_PROMPT_DYNAMIC_BOUNDARY = '__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__'
```

分段通过 `systemPromptSection()` + `resolveSystemPromptSections()` 实现，静态部分使用 `cacheScope: 'global'` 跨会话共享缓存。

### 4.2 关键 Prompt 技巧

**代码风格指导**（Anthropic 内部版独有）：
```
Default to writing no comments. Only add one when the WHY is non-obvious:
a hidden constraint, a subtle invariant, a workaround for a specific bug...
Don't explain WHAT the code does, since well-named identifiers already do that.
```

**反虚假声明**（Capybara v8 对策）：
```
Report outcomes faithfully: if tests fail, say so with the relevant output;
if you did not run a verification step, say that rather than implying it succeeded.
Never claim "all tests pass" when output shows failures.
```

**最小复杂度原则**：
```
Don't create helpers, utilities, or abstractions for one-time operations.
Three similar lines of code is better than a premature abstraction.
```

**验证代理契约**（Feature-gated）：
```
When non-trivial implementation happens, independent adversarial verification
must happen before you report completion. Spawn AgentTool with
subagent_type="verification_agent". Your own checks do NOT substitute.
```

### 4.3 Compact Prompt（src/services/compact/prompt.ts）

完整的 9 段摘要模板：
1. Primary Request and Intent
2. Key Technical Concepts
3. Files and Code Sections（含代码片段）
4. Errors and fixes
5. Problem Solving
6. All user messages
7. Pending Tasks
8. Current Work
9. Optional Next Step

使用 `<analysis>` 作为草稿区，`<summary>` 作为最终输出，`formatCompactSummary()` 会剥离 analysis 块。

**NO_TOOLS_PREAMBLE**：压缩时禁止工具调用（模型在 Sonnet 4.6+ 上会错误尝试工具调用，浪费仅有的 turn）。

---

## 五、上下文压缩系统

### 5.1 四层压缩策略

```
消息 → Snip → MicroCompact → ContextCollapse → AutoCompact
```

1. **Snip**（feature-gated `HISTORY_SNIP`）：行级裁剪，删除历史消息中不再需要的内容
2. **MicroCompact**：压缩大型工具结果（文件读取、搜索结果等）
   - 基于时间和工具类型配置（`timeBasedMCConfig`）
   - 仅压缩特定工具：FileRead、Bash、Grep、Glob、WebSearch、WebFetch、FileEdit、FileWrite
   - **缓存编辑**（`CACHED_MICROCOMPACT`）：直接操作 API 缓存而非重发完整上下文
3. **ContextCollapse**（feature-gated `CONTEXT_COLLAPSE`）：细粒度上下文折叠
   - 基于 commit log 的投影视图
   - 比 auto-compact 更精细（保留粒度而非单一摘要）
4. **AutoCompact**：完整摘要压缩
   - 使用独立的 API 调用生成摘要
   - 阈值基于 `tokenCountWithEstimation(messages)` 计算
   - 支持 partial compact（仅压缩最近部分）

### 5.2 缓存编辑（Ant-only 高级特性）

```typescript
// cachedMicrocompact.ts
// 不重发完整上下文，而是直接告诉 API 缓存哪些输入已被替换
// 通过 cache_deletion 和 cache_reference 机制实现
```

这是一个非常巧妙的设计：直接修改 prompt cache 而非重建上下文，大幅节省 token 成本。

---

## 六、权限与安全系统

### 6.1 三层权限

```
1. 工具级权限 → checkPermissions() → PermissionDecision
2. 文件系统权限 → matchWildcardPattern()
3. 命令权限 → yoloClassifier（AI 分类器）
```

### 6.2 YOLO Classifier（Auto Mode）

使用独立的 AI 调用对工具使用进行安全分类：

```typescript
// yoloClassifier.ts
// 使用 sideQuery() 并行发起分类请求
// 基于 auto_mode_system_prompt.txt 中的规则模板
// 支持用户自定义 allow/soft_deny/environment 规则
```

**危险权限检测**：
- `isDangerousBashPermission()`: 检查 `python:*`, `node:*`, `bash -c` 等模式
- `isDangerousPowerShellPermission()`: 检查 `iex`, `Invoke-Expression`, `Start-Process` 等

### 6.3 权限模式

```typescript
type PermissionMode = 'default' | 'plan' | 'autoEdit' | 'fullAuto' | 'bypassPermissions'
```

- **Plan Mode**: 需要计划审批
- **AutoEdit**: 自动允许文件编辑
- **FullAuto**: 自动允许所有工具（受 yoloClassifier 约束）

---

## 七、MCP 客户端（src/services/mcp/client.ts）

### 传输层支持
- **StdioClientTransport**: 标准输入输出
- **SSEClientTransport**: Server-Sent Events
- **StreamableHTTPClientTransport**: 可流式 HTTP
- **WebSocketTransport**: 自定义 WebSocket
- **SdkControlTransport**: IDE SDK 控制

### 关键功能
- OAuth 认证流程（`ClaudeAuthProvider`）
- MCP 技能发现（feature-gated `MCP_SKILLS`）
- 大输出持久化（`persistBinaryContent`）
- 二进制内容处理（图片自动缩放/降采样）
- 连接状态追踪（`needs-auth` / `connected`）

---

## 八、Session Memory（src/services/SessionMemory/）

### 设计理念
后台子代理自动维护会话笔记文件，不打断主对话流。

```typescript
// 触发条件：
// 1. 初始化阈值（首次）
// 2. token 增长阈值（更新）
// 3. 工具调用次数阈值

export function shouldExtractMemory(messages: Message[]): boolean {
  const currentTokenCount = tokenCountWithEstimation(messages)
  if (!isSessionMemoryInitialized() && !hasMetInitializationThreshold(currentTokenCount))
    return false
  if (!hasMetUpdateThreshold(currentTokenCount)) return false
  // ...
}
```

使用 `runForkedAgent()` 在后台运行提取，结果写入会话 memory 目录。

---

## 九、Magic Docs（src/services/MagicDocs/）

自动维护带有特殊头部的 markdown 文档：

```markdown
# MAGIC DOC: API Design Decisions
_Keep this doc updated as the codebase evolves_
```

当文件被读取时自动注册，后台通过 `runAgent()` 更新文档内容。

---

## 十、Hooks 系统（src/utils/hooks.ts）

### Hook 类型
```
SessionStart → InstructionsLoaded → UserPromptSubmit → PreToolUse → 
PostToolUse → PostToolUseFailure → PermissionDenied → PermissionRequest →
PreCompact → PostCompact → SubagentStart → SubagentStop →
SessionEnd → Stop → StopFailure → TaskCreated → TaskCompleted →
TeammateIdle → ConfigChange → CwdChanged → FileChanged →
Elicitation → ElicitationResult → StatusLine → FileSuggestion
```

### 执行模式
- **同步 Hook**: 阻塞等待结果
- **异步 Hook**: 后台执行，结果通过事件通知
- **Prompt Hook**: 返回修改后的 prompt
- **Agent Hook**: 启动 AI 代理处理

### 超时控制
- 工具 Hook: 10 分钟
- SessionEnd Hook: 1.5 秒（可配置）

---

## 十一、插件系统（src/utils/plugins/）

### 插件结构
```
my-plugin/
├── plugin.json          # 元数据清单
├── commands/            # 自定义斜杠命令
├── agents/              # 自定义 AI 代理
└── hooks/               # Hook 配置
```

### 加载策略
1. 内置插件（`builtinPlugins`）
2. Marketplace 插件（`plugin@marketplace` 格式）
3. Git 仓库插件
4. Session 插件（`--plugin-dir` CLI 标志）

### 安全机制
- Marketplace 白名单/黑名单
- `validatePathWithinBase()` 防止路径遍历
- ZIP 缓存隔离
- 版本化缓存路径

---

## 十二、Swarm / 多 Agent 系统

### 队友系统（src/utils/swarm/inProcessRunner.ts）

```typescript
// 运行队友代理：
// 1. AsyncLocalStorage 上下文隔离（runWithTeammateContext）
// 2. 邮箱系统通信（readMailbox/writeToMailbox）
// 3. 权限同步（permissionSync.ts）
// 4. 计划模式审批流程
// 5. 空闲通知 leader
```

### 邮箱通信
- `readMailbox()`: 读取消息
- `writeToMailbox()`: 发送消息
- `createIdleNotification()`: 空闲通知
- `isPermissionResponse()`: 权限回复识别
- `isShutdownRequest()`: 关闭请求识别

### Fork 子代理
- Git worktree 隔离
- 后台运行 + 进度通知
- `removeAgentWorktree()` 清理

---

## 十三、API 层（src/services/api/claude.ts）

### Prompt Caching
```typescript
cache_control: getCacheControl({ querySource })
// 每个请求恰好一个 message-level cache_control marker
// API 要求 cache_reference 出现在最后一个 cache_control "之前或之上"
```

### 重试策略（withRetry.ts）
- 默认最大重试 10 次
- 529 错误最多重试 3 次
- 前台查询源（用户等待的结果）才重试
- 基础延迟 500ms + 指数退避
- 持久模式（ant-only）：无限重试 + 5分钟最大退避 + 30秒心跳

### Feature Gates
使用 `feature('FEATURE_NAME')` 实现编译期死代码消除：
```typescript
const reactiveCompact = feature('REACTIVE_COMPACT')
  ? (require('./services/compact/reactiveCompact.js') as ...)
  : null
```

未启用的功能在构建时完全排除，零运行时开销。

---

## 十四、Prompt Suggestion（src/services/PromptSuggestion/）

使用 **投机执行**（speculation）预计算下一个 prompt 建议：

```typescript
// 用户输入时立即启动后台 API 调用预测可能的下一步
// 通过 abortController 在用户实际输入时取消
export function shouldEnablePromptSuggestion(): boolean {
  // 需要 GrowthBook gate 'tengu_chomp_inflection'
  // 交互模式下启用，非交互模式禁用
  // Swarm 队友禁用（仅 leader 显示建议）
}
```

---

## 十五、关键设计模式总结

### 1. Feature Flags 作为架构工具
不是简单的开关，而是 **编译期代码消除**。`feature('XXX')` 在构建时完全排除未启用的代码路径，实现零成本功能开关。

### 2. 四层上下文压缩
从轻量到重量：Snip → MicroCompact → ContextCollapse → AutoCompact。每一层独立决策，组合使用。

### 3. 缓存编辑
直接操作 prompt cache 而非重建上下文。这是 Anthropic 内部独有的高级特性，外部版本没有。

### 4. 异步生成器驱动的 Agent Loop
`async function* query()` 让整个循环可以被 yield/pause/abort，天然支持流式输出和中断。

### 5. System Prompt 分段缓存
静态部分跨会话共享，动态部分每会话生成。通过 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 分隔。

### 6. 权限分类器
不依赖硬编码规则，而是使用 AI 对工具使用进行安全分类，支持用户自定义规则。

### 7. 子代理隔离
Git worktree + AsyncLocalStorage + 邮箱通信，实现真正的并行安全执行。

### 8. Prompt 工程最佳实践
- 使用 `<analysis>` 草稿区让模型先思考再输出
- Few-shot 示例（`<example>` 标签）
- 针对模型版本的特定对策（`@[MODEL LAUNCH]` 注释标记更新点）
- 防御性指令（"Don't claim X if you didn't verify"）

---

## 十六、可借鉴的最佳实践

### 对 OpenClaw/个人助手的启示

1. **四层压缩架构**：当前 LCM 系统可借鉴 snip → microcompact → collapse → full-compact 的分层策略
2. **Feature gate 死代码消除**：用构建时排除替代运行时判断
3. **System prompt 缓存分段**：静态全局缓存 + 动态会话缓存分离
4. **Fork 子代理模式**：worktree 隔离 + 邮箱通信 + 进度追踪
5. **安全分类器**：用 AI 而非硬规则做权限判断
6. **Prompt 对策注释**：每次模型更新都标注需要调整的 prompt 部分（`@[MODEL LAUNCH]`）
7. **缓存编辑**：直接操作 API 缓存层而非重建上下文

---

*报告完成。源码规模庞大，本报告聚焦最核心的架构设计和实现细节。*
