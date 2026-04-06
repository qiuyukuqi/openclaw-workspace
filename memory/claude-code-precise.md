# Claude Code 精读笔记 — 代码级细节与可落地改进

> 第三轮精读，聚焦prompt措辞、算法逻辑、错误处理、设计模式
> 日期：2026-04-07

---

## 第一批：Prompt工程

### 1. src/constants/prompts.ts (914行)

**核心功能**: Claude Code的完整system prompt生成器，包含12+个section，按静态/动态边界分组。

**关键设计**:
- **SYSTEM_PROMPT_DYNAMIC_BOUNDARY**: 将prompt分为static（可全局缓存）和dynamic两部分，静态部分不变时可复用cache prefix hash
- **feature() DCE模式**: 用 `process.env.USER_TYPE === 'ant'` 在编译时内联消除外部build中的ant-only prompt
- **DEAD CODE ELIMINATION**: `const module = feature('X') ? require(...) : null` — 条件导入减少bundle size

**可落地改进**:
1. **Prompt Cache优化**: OpenClaw的system prompt应仿照BOUNDARY模式，将环境相关部分(时间、工作目录)放到最后，保持前缀不变以提升cache命中率
2. **False Claims防护** (ant-only,已验证有效): `Report outcomes faithfully: if tests fail, say so with the relevant output; never claim "all tests pass" when output shows failures` — 直接加入我们的SOUL.md
3. **Numeric Length Anchors**: `Length limits: keep text between tool calls to ≤25 words. Keep final responses to ≤100 words` — 研究显示~1.2%输出token减少
4. **代码风格指令**值得全文借鉴:
   - `Three similar lines of code is better than a premature abstraction`
   - `Don't add docstrings, comments, or type annotations to code you didn't change`
   - `Default to writing no comments. Only add one when the WHY is non-obvious`
   - `Before reporting a task complete, verify it actually works`
5. **Actions Section**: 完整的风险分级框架 — destructive/hard-to-reverse/visible-to-others 三类，每类都有具体例子
6. **Undercover模式**: `isUndercover()` 在system prompt中完全隐藏模型名称/ID，防止内部代号泄露到公开PR/commit

**关键代码**:
```typescript
// 编译时常量折叠 — MUST内联在每个调用点，不能hoist到const
// 否则bundler无法DCE
if (process.env.USER_TYPE === 'ant' && isUndercover()) {
  // suppress model name
} else {
  const marketingName = getMarketingNameForModel(modelId)
  modelDescription = marketingName
    ? `You are powered by the model named ${marketingName}.`
    : `You are powered by the model ${modelId}.`
}
```

---

### 2. src/constants/prompts/toolDescriptions.ts

**核心功能**: 工具描述prompt，每个工具的description都经过精心措辞。

**可落地改进**: 工具描述中嵌入使用指导，而非单纯的功能说明。例如FileEditTool的描述包含"必须先Read"的约束，直接在描述层面防错。

---

### 3. src/services/compact/prompt.ts (374行)

**核心功能**: 会话压缩的prompt模板，支持BASE（全量压缩）和PARTIAL（增量压缩）两种模式。

**关键设计**:
- **NO_TOOLS_PREAMBLE**: 压缩agent使用 `maxTurns: 1`，如果模型尝试调工具会被拒绝导致失败。Sonnet 4.6+的自适应thinking模型会尝试调工具(2.79% vs 0.01%)，所以把"CRITICAL: Respond with TEXT ONLY"放在最前面
- **analysis标签模式**: `<analysis>` 是drafting scratchpad，`formatCompactSummary()` 会在输出中strip掉，最终只保留 `<summary>`
- **9-section结构**: Primary Request → Technical Concepts → Files → Errors → Problem Solving → User Messages → Pending Tasks → Current Work → Next Step
- **Next Step约束**: `IMPORTANT: ensure this step is DIRECTLY in line with the user's most recent explicit requests` + 要求引用原文verbatim防drift

**可落地改进**:
1. **OpenClaw LCM压缩可以借鉴这个9-section结构**，尤其是"Errors and fixes"和"All user messages"两个section
2. **NO_TOOLS_PREAMBLE技巧**: 对任何maxTurns=1的子agent，都要在prompt开头明确声明"不要调工具"和失败后果
3. **PARTIAL模式**: 当只压缩recent messages时，明确告诉模型"earlier messages are being kept intact and do NOT need to be summarized"

**关键代码**:
```typescript
const NO_TOOLS_PREAMBLE = `CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.`
```

---

### 4. src/services/SessionMemory/prompts.ts (324行)

**核心功能**: Session Memory的模板和更新prompt。

**关键设计**:
- **10-section模板**: Session Title, Current State, Task Specification, Files and Functions, Workflow, Errors & Corrections, Codebase Documentation, Learnings, Key Results, Worklog
- **结构保护**: "NEVER modify, delete, or add section headers" — 用斜体描述行作为模板指令
- **Token预算**: MAX_SECTION_LENGTH=2000, MAX_TOTAL=12000，超限时强制精简
- **自定义覆盖**: `~/.claude/session-memory/config/template.md` 和 `prompt.md`

**可落地改进**:
1. **OpenClaw的MEMORY.md结构已参考此模板**，但可以加入token预算监控（MAX_SECTION_LENGTH限制）
2. **"IMPORTANT: Always update 'Current State'"** — 这个在每次更新时都强调，确保跨轮连续性
3. **Key Results section**: 用户要求特定输出时，要求完整精确复制结果而非总结

**关键代码**:
```typescript
function generateSectionReminders(sectionSizes, totalTokens): string {
  const overBudget = totalTokens > MAX_TOTAL_SESSION_MEMORY_TOKENS
  // CRITICAL级提醒：总量超限时强制精简
  // 超长section按token排序，优先精简最大的
  const oversizedSections = Object.entries(sectionSizes)
    .filter(([_, tokens]) => tokens > MAX_SECTION_LENGTH)
    .sort(([, a], [, b]) => b - a)
    .map(([section, tokens]) =>
      `- "${section}" is ~${tokens} tokens (limit: ${MAX_SECTION_LENGTH})`)
}
```

---

### 5. src/services/autoDream/consolidationPrompt.ts (65行)

**核心功能**: AutoDream记忆整合的4阶段prompt模板。

**可落地改进**:
1. **4阶段模式已参考**，但prompt中的具体措辞值得学习:
   - "Merging new signal into existing topic files rather than creating near-duplicates"
   - "Converting relative dates to absolute dates so they remain interpretable after time passes"
   - "Deleting contradicted facts — if today's investigation disproves an old memory, fix it at the source"
2. **Transcript搜索指导**: `grep -rn "<narrow term>" ${transcriptDir}/ --include="*.jsonl" | tail -50` — 明确告诉模型只grep窄术语，不要读整个transcript
3. **索引维护**: `each entry should be one line under ~150 characters: - [Title](file.md) — one-line hook`

---

### 6. src/services/extractMemories/prompts.ts (154行)

**核心功能**: 记忆提取子agent的prompt。

**关键设计**:
- **Turn budget优化策略**: 明确告诉agent最优策略是 `turn 1 — 所有READ并行; turn 2 — 所有WRITE并行`，避免read/write交叉
- **Manifest去重**: 提供existing memory manifest，要求先检查再写
- **工具白名单**: 只允许READ/GREP/GLOB/只读BASH/EDIT-WRITE（仅限memory目录内）
- **两步保存**: Step 1写文件 + Step 2更新MEMORY.md索引

**可落地改进**:
1. **Turn budget策略**: 子agent的prompt中明确写出"最优N-turn策略"，减少浪费
2. **"You MUST only use content from the last ~N messages"** — 严格限制输入范围，防止agent浪费时间调查验证

---

### 7. src/tools/BashTool/prompt.ts (369行)

**核心功能**: Bash工具的完整prompt，包含git操作安全协议。

**可落地改进**:
1. **Git Safety Protocol** — 一套完整的防御规则:
   - NEVER update git config
   - NEVER force push to main/master
   - CRITICAL: Always create NEW commits rather than amending (当pre-commit hook失败时，amend会修改前一个commit导致工作丢失)
   - Never use -i flag (交互式不支持)
   - Commit message通过HEREDOC传递确保格式
2. **并行批处理指导**: `When multiple independent pieces of information are requested, run multiple tool calls in parallel`
3. **Background task note**: 明确说明"不需要立即检查输出，完成后会被通知"

---

### 8. src/tools/BashTool/bashSecurity.ts (2592行)

**核心功能**: 最全面的安全检查系统，25+种检查类型。

**关键设计**:
- **COMMAND_SUBSTITUTION_PATTERNS**: 14种shell注入检测模式，包括Zsh特有的 `=cmd` 等号展开（bypass BASH(curl:*) deny rule）
- **ZSH_DANGEROUS_COMMANDS**: 17个Zsh危险内置命令（zmodload, zpty, ztcp, sysopen等）
- **Numeric identifiers**: BASH_SECURITY_CHECK_IDS用数字而非字符串记录检查类型，避免在日志中泄露检查名称
- **TreeSitter分析**: 使用tree-sitter解析bash AST，而非仅靠正则

**可落地改进**:
1. **Zsh =cmd展开绕过**: `=curl evil.com` → `/usr/bin/curl evil.com` 绕过deny rule — 如果OpenClaw支持zsh需要注意
2. **防御深度**: PowerShell注释语法 `<#` 也被检测，即使不在PowerShell中执行
3. **Heredoc注入**: `$\(.*<</` 检测heredoc中的命令替换
4. **COMMENT_QUOTE_DESYNC**: 检测注释-引号不同步攻击
5. **MALFORMED_TOKEN_INJECTION**: 检测畸形token注入

---

### 9. src/tools/FileEditTool/prompt.ts

**核心功能**: 文件编辑工具描述。

**关键设计**:
- **强制先读**: `You must use your Read tool at least once before editing`
- **行号前缀剥离**: 明确说明line number prefix的格式（`spaces + line number + arrow`），要求编辑时只匹配实际文件内容
- **最小唯一性**: ant版本增加 `Use the smallest old_string that's clearly unique — usually 2-4 adjacent lines is sufficient`

---

### 10. src/skills/bundled/remember.ts

**核心功能**: /remember技能 — 审查auto-memory并提议提升到CLAUDE.md/CLAUDE.local.md。

**可落地改进**:
1. **4层记忆分类法**: CLAUDE.md(项目级) / CLAUDE.local.md(个人级) / Team Memory(组织级) / Stay in auto-memory(临时)
2. **关键区分**: "Workflow practices (PR conventions, merge strategies, branch naming) are ambiguous — ask the user whether they're personal or team-wide"
3. **先提案后执行**: "Present ALL proposals before making any changes" — 对用户可见的操作一定要先审批

---

### 11. src/skills/bundled/stuck.ts

**核心功能**: /stuck技能 — 诊断冻结的Claude Code会话。

**可落地改进**:
1. **诊断方法**:
   - 高CPU(≥90%)持续 → 无限循环（采样两次确认非瞬态）
   - 进程状态D → I/O挂起
   - RSS≥4GB → 内存泄漏
   - 子进程挂起 → `pgrep -lP <pid>`
2. **两消息结构**: 顶层消息一行摘要（hostname+version+症状），thread回复完整诊断
3. **macOS stack dump**: `sample <pid> 3` 获取3秒native stack sample

---

### 12. src/skills/bundled/batch.ts

**核心功能**: /batch技能 — 大规模并行修改编排器。

**可落地改进**:
1. **3阶段模式**: Research+Plan → Spawn Workers → Track Progress
2. **Worktree隔离**: 所有worker使用 `isolation: "worktree"` — 每个在独立git worktree中工作
3. **Worker指令模板**: simplify → unit test → e2e test → commit+push+PR → report `PR: <url>`
4. **e2e测试必须确定**: "Do not skip this — the workers cannot ask the user themselves"
5. **MIN_AGENTS=5, MAX_AGENTS=30**: 根据实际工作量调整agent数量

---

## 第二批：核心逻辑

### 13. src/query.ts (1731行)

**核心功能**: Claude Code的核心query loop — 整个agentic循环的心脏。

**关键设计**:
- **Generator函数**: `async function* query()` — 通过yield向调用者流式返回消息
- **多层压缩管道**: snip → microcompact → contextCollapse → autocompact — 按序执行，每步都可能减少token
- **MAX_OUTPUT_TOKENS_RECOVERY_LIMIT=3**: max_output_tokens错误最多恢复3次
- **Withholding机制**: `isWithheldMaxOutputTokens()` — 对SDK调用者暂时隐藏错误，等recovery loop完成
- **Token Budget追踪**: 跨compaction边界追踪task_budget.remaining
- **dumpPromptsFetch**: 每个query session只创建一次fetch wrapper，避免内存泄漏（~500MB/session）
- **工具结果预算**: `applyToolResultBudget()` 在microcompact之前执行，对工具结果大小设限
- **model动态切换**: plan模式下如果最近assistant消息>200k token，自动切换模型

**可落地改进**:
1. **多层压缩管道模式**: OpenClaw可以借鉴这种按优先级排列的压缩链
2. **Withholding模式**: 错误不立即暴露给外部调用者，先尝试内部恢复
3. **Query tracking**: chainId + depth 追踪查询链，用于analytics关联
4. **Context collapse**: 用projection而非mutation — collapsed view是read-time projection，summary消息存在独立store中

---

### 14. src/utils/yoloClassifier.ts (→ permissions/yoloClassifier.ts)

**核心功能**: YOLO模式的命令安全分类器 — 决定哪些bash命令可以自动执行。

**关键设计**: 将bash命令格式化为分类器输入，判断是否可以自动执行而无需用户确认。

**可落地改进**: OpenClaw的exec权限检查可以借鉴这种"先分类再决定"的模式，而非简单的白名单。

---

### 15. src/utils/permissions/permissions.ts (1337+行)

**核心功能**: 完整的权限系统，支持多源规则、分类器集成、拒绝追踪。

**关键设计**:
- **多源规则**: cliArg, command, session, project, org, user, managed — 优先级从低到高
- **Denial Tracking**: `DENIAL_LIMITS` — 连续被拒绝后自动降级到prompt模式（fallback到询问用户）
- **Classifier集成**: 当classifier不可用时fail-closed（30分钟refresh周期）
- **PermissionRuleValue**: 支持多种匹配模式（exact, glob, regex等）

**可落地改进**:
1. **Denial Tracking + Fallback**: 连续N次工具被拒绝后自动切换策略，而非无限重试
2. **多源权限合并**: 不同来源的allow/deny规则按优先级合并

---

### 16. src/context/contextManager.ts

**核心功能**: 上下文管理器 — 管理会话的消息历史和token预算。

**可落地改进**: token counting使用 `tokenCountWithEstimation()` 混合精确和估算，避免每次都调API。

---

### 17. src/utils/hooks.ts

**核心功能**: Hook系统 — 用户定义的shell命令在Claude Code生命周期各阶段执行。

**关键设计**:
- **Hook事件类型**: PreToolUse, PostToolUse, PostToolUseFailure, PermissionDenied, PreCompact, PostCompact, SessionStart, SessionEnd, Stop, StopFailure, SubagentStart/Stop, TeammateIdle, TaskCreated/Completed, ConfigChange, CwdChanged, FileChanged, InstructionsLoaded
- **JSON output schema**: hook可以返回结构化的JSON输出（如修改prompt、阻止工具调用）
- **Async hooks**: 支持异步hook（如等待外部审批）

**可落地改进**: OpenClaw的hook系统可以支持更多事件类型（尤其是PreToolUse和PermissionDenied）。

---

### 18. src/utils/swarm/inProcessRunner.ts (1553行)

**核心功能**: Swarm队友的进程内运行器 — 封装runAgent()提供AsyncLocalStorage隔离、进度跟踪、权限同步。

**关键设计**:
- **AsyncLocalStorage隔离**: `runWithTeammateContext()` 每个teammate有独立上下文
- **Mailbox通信**: `readMailbox()` / `writeToMailbox()` 异步消息传递
- **Permission同步**: leader的权限更新同步到teammate
- **Idle notification**: 完成时通知leader
- **AbortController**: 两级abort — whole-task和current-turn

**可落地改进**:
1. **两级abort模式**: 一个abortController杀整个task，另一个只杀当前turn
2. **Mailbox通信**: 简单的read/write文件系统消息传递，适合进程内协调
3. **Progress tracking**: 通过 `createProgressTracker()` 创建进度跟踪器

---

## 第三批：工具实现

### 19. src/tools/AgentTool/ (4514行总计)

**核心功能**: AgentTool — 子agent执行框架，支持fork/teammate/explore等多种模式。

**关键设计**:
- **Fork模式**: `isolation: "worktree"` — 在独立git worktree中运行，工具输出不污染主上下文
- **Agent list injection**: 动态agent列表通过attachment消息注入而非工具描述，避免cache bust（占10.2% cache tokens）
- **Memory snapshot**: fork启动时克隆主agent的memory状态
- **Explore agent**: 深度代码探索专用，设置 `EXPLORE_AGENT_MIN_QUERIES` 阈值

**可落地改进**:
1. **Agent list通过attachment注入**而非嵌入工具描述 — 减少cache bust
2. **Memory snapshot on fork**: 子agent继承主agent的记忆快照

---

### 20. src/utils/ultraplan/ccrSession.ts

**核心功能**: ULTRAPLAN的轮询会话 — 等待浏览器端Plan Mode审批。

**关键设计**:
- **ExitPlanModeScanner**: 纯状态分类器，无I/O无定时器 — 可单元测试和离线回放
- **优先级**: approved > terminated > rejected > pending > unchanged
- **MAX_CONSECUTIVE_FAILURES=5**: 轮询最多连续失败5次
- **UltraplanPhase**: running → needs_input → plan_ready 状态机

---

### 21. src/services/MagicDocs/

**核心功能**: Magic Docs — 自动维护项目文档。

**关键设计**:
- **自定义prompt**: `~/.claude/magic-docs/prompt.md` 覆盖默认模板
- **{{variable}}语法**: 单次替换避免双重替换bug（`$ backreference corruption` + `double-substitution when user content contains {{varName}}`）
- **Documentation哲学**: "BE TERSE. High signal only" + 只记录WHY/HOW/WHERE，不记录详细代码步骤

**可落地改进**:
1. **单次替换**: 用 `replace(/\{\{(\w+)\}\}/g, ...)` 而非链式replace，避免双重替换漏洞
2. **"Keep the document CURRENT"**: 明确说"不是changelog，是当前状态"

---

### 22. src/tasks/DreamTask/DreamTask.ts

**核心功能**: DreamTask — auto-dream记忆整合的后台任务，纯UI展示层。

**关键设计**:
- **Phase detection**: 'starting' → 'updating'（当第一个Edit/Write工具调用时触发）
- **filesTouched**: 通过onMessage pattern-match捕获Edit/Write中的文件路径
- **注释**: "This is an INCOMPLETE reflection of what the dream agent actually changed — treat as 'at least these were touched'"
- **MAX_TURNS=30**: 只保留最近30个turn的显示

---

### 23. src/coordinator/coordinatorMode.ts

**核心功能**: Coordinator模式 — 主agent调度worker agent的模式。

**关键设计**:
- **INTERNAL_WORKER_TOOLS**: TeamCreate, TeamDelete, SendMessage, SyntheticOutput — 只有coordinator能用的工具
- **Scratchpad gate**: `isScratchpadGateEnabled()` — coordinator有自己的临时目录
- **Session mode匹配**: 恢复session时自动匹配coordinator/normal模式

---

## 综合发现 — 前两轮遗漏的重要设计

### 1. Context Collapse (全新发现)
`feature('CONTEXT_COLLAPSE')` — 在autocompact之前运行的"轻量级压缩"：
- 用projection而非mutation（read-time projection over REPL history）
- Summary存在独立store中，不修改原始消息数组
- 跨turn持久化：`projectView()` 每次entry回放commit log

### 2. Snip Compact (全新发现)  
`feature('HISTORY_SNIP')` — 在microcompact之前运行，裁剪消息历史中的冗余部分
- snipTokensFreed传递给autocompact，让阈值检查反映已释放的token

### 3. Cached Microcompact (全新发现)
`feature('CACHED_MICROCOMPACT')` — 通过编辑prompt cache而非重新生成来压缩
- `pendingCacheEdits` 在API响应后执行，使用实际的cache_deleted_input_tokens
- `keepRecent` 最近的N个工具结果始终保留

### 4. Proactive Mode (全新发现)
`feature('PROACTIVE')` — 自主工作模式：
- `<tick>` 提示保持agent活跃
- `SLEEP_TOOL` 控制唤醒间隔
- "If you have nothing useful to do, you MUST call SLEEP" — 避免浪费turn
- "Bias toward action" — 读文件、运行测试、提交代码都无需确认

### 5. Verification Agent (全新发现)
`feature('VERIFICATION_AGENT')` — 非trivial实现后自动spawn独立验证agent
- "Non-trivial means: 3+ file edits, backend/API changes, or infrastructure changes"
- 自己的检查不算，必须由独立verifier给出verdict
- PASS时要spot-check: 重新运行2-3个命令确认结果
- FAIL时要修复并重新验证

### 6. Token Budget系统
API task_budget + 自定义+500k auto-continue：
- 每turn显示output token count
- 跨compaction边界追踪remaining
- 到达target后系统自动继续（不会提前停止）

---

## 最高优先级行动项

| # | 改进 | 来源文件 | 预期效果 |
|---|------|----------|----------|
| 1 | System prompt BOUNDARY cache优化 | prompts.ts | 提升prompt cache命中率 |
| 2 | False Claims防护措辞加入SOUL.md | prompts.ts | 减少虚假成功报告 |
| 3 | 压缩prompt的9-section结构 | compact/prompt.ts | 改善LCM压缩质量 |
| 4 | NO_TOOLS_PREAMBLE for maxTurns=1 agents | compact/prompt.ts | 防止子agent浪费turn |
| 5 | Turn budget优化策略写入子agent prompt | extractMemories/prompts.ts | 减少子agent token浪费 |
| 6 | Token budget监控加入MEMORY.md | SessionMemory/prompts.ts | 防止记忆文件膨胀 |
| 7 | 验证Agent模式 | prompts.ts (VERIFICATION_AGENT) | 非trivial实现自动验证 |
| 8 | 多层压缩管道 | query.ts | snip→micro→collapse→auto |
| 9 | Withholding错误恢复模式 | query.ts | 提升用户体验 |
| 10 | Denial Tracking自动降级 | permissions.ts | 避免无限重试被拒工具 |
