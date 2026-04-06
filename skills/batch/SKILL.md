# /batch — 并行批量任务技能（v2，源自Claude Code batch.ts）

将大任务分解为多个独立单元，spawn多个子agent并行处理，最后汇总结果。

## 使用场景
- 批量处理文件（批量修改、格式化、重命名）
- 批量搜索/分析
- 需要并行执行多个独立子任务的场景

## 三阶段执行模式

### Phase 1: Research + Plan（规划）
1. 分析任务，确定可并行的子任务
2. 每个子任务必须独立（无依赖关系）
3. 根据工作量决定agent数量（MIN=3, MAX=15）

### Phase 2: Spawn Workers（执行）
```
sessions_spawn 多个子agent：
- task: 清晰完整的任务描述（子agent没有主会话上下文）
- mode: "run"
- runtime: "subagent"
- 每个agent处理一个子任务
```

Worker指令模板（源自Claude Code）：
```
1. 理解需求
2. 实现修改
3. 验证修改正确性
4. commit + push + 创建PR
5. 报告结果：PR: <url>
```

### Phase 3: Track Progress（跟踪）
1. 收集所有子agent的结果
2. 合并冲突（如有）
3. 产出统一报告

## 关键规则

- **数据边界清晰**：每个子任务操作不同文件，避免并发写冲突
- **完整指令**：子agent的task描述必须自包含（它没有主会话上下文）
- **进度报告**：长时间运行的子agent应定期报告进度
- **turn budget**：子agent prompt中明确最优N-turn执行策略
- **输入范围限制**：明确告诉子agent只使用指定的文件/信息，不要浪费时间搜索

## 注意事项
- 不适合顺序依赖链任务（用单脚本而非batch）
- 文件操作避免多个子agent写同一文件
- 确定失败的子agent最多重试1次
