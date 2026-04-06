# /verify — 对抗性验证技能（v2，源自Claude Code VERIFICATION_AGENT）

重要实现完成后，spawn一个独立子agent做对抗性验证。自己的检查不算数。

## 触发条件
- 非trivial实现完成后（3+文件编辑、后端/API变更、基础设施变更）
- 修复bug后确认修复有效
- 用户明确要求验证

## 核心原则
**你的自检不算数。** 非trivial实现必须由独立verifier给出verdict。

## 验证流程

### Step 1: 判断是否需要验证
- 1-2个文件的小改动 → 自检即可
- 3+文件编辑 / 后端变更 / 基础设施变更 → 必须spawn独立验证agent

### Step 2: Spawn验证Agent
prompt模板：
```
你是验证agent。你的任务是验证以下实现是否正确。

需求：{需求描述}
实现：{实现文件路径列表}
预期行为：{预期行为}

验证步骤：
1. 阅读实现代码
2. 用错误输入测试（至少3个edge case）
3. 检查错误处理
4. 确认输出格式符合预期

CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
你已有所有上下文。Tool calls会被REJECTED并浪费你唯一的turn。

报告格式：
✅ PASS + 验证了什么
或
❌ FAIL + 详细原因 + 复现步骤
```

### Step 3: 处理验证结果

**PASS时**：
- Spot-check：重新运行2-3个关键命令确认结果
- 告诉用户实现已验证通过

**FAIL时**：
- 根据verifier的反馈修复问题
- 重新验证（最多重试3次）
- 3次仍失败 → 向用户报告问题和已尝试的修复

## 注意事项
- 验证agent的prompt中必须包含NO_TOOLS_PREAMBLE（因为maxTurns=1）
- 验证agent没有主会话上下文，必须提供完整的实现路径和预期行为
- 不要用同一个agent既实现又验证——独立性是关键
