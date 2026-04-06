# /extract — 对话后记忆提取技能（v2，源自Claude Code Extract Memories）

在重要对话结束后，提取本次对话中遗漏或值得长期记住的信息。

## 使用场景
- 完成一个复杂任务后（发布流水线、系统配置、问题排查）
- 学到新知识/踩到新坑后
- 用户明确要求"记住这个"时

## 触发条件
1. 本次对话产生了新的工具命令/脚本/配置
2. 本次对话修复了bug或解决了问题
3. 用户说了"记住"、"记一下"
4. 距上次提取超过24小时且有非trivial对话

## 执行流程

### Step 1: 回顾本次对话
浏览对话历史中的关键决策、错误、解决方案。**严格限制范围**：只使用最近N条消息的内容，不要浪费时间调查更早的上下文。

### Step 2: 检查现有记忆（Manifest去重）
- 读取MEMORY.md当前内容
- 如果要存储的信息已有类似条目，更新而非创建重复
- 矛盾事实以较新的为准

### Step 3: 分类存储

按类型存入对应位置：

| 信息类型 | 存储位置 | 格式 |
|---------|---------|------|
| 规则/铁律 | MEMORY.md 铁律section | Rule格式 |
| 错误修复 | MEMORY.md 错误与修复section | 问题→修复格式 |
| 工作流 | MEMORY.md 工作流section | 命令/步骤格式 |
| 项目信息 | MEMORY.md 关键项目section | 表格格式 |
| 通用知识 | MEMORY.md 通用知识section | 要点格式 |
| 快速检索 | LanceDB memory_store | 原子化条目(<500字符) |

### Step 4: 去重验证
- 检查MEMORY.md是否已有类似内容
- 重要条目同时存LanceDB（用memory_recall验证可检索）
- MEMORY.md每个section保持在合理长度（超30行需精简旧条目）

### Step 5: 更新Current State
- 更新MEMORY.md的Current State section
- 反映最新的工作状态和下一步计划

## Turn Budget优化策略
当使用子agent执行提取时，prompt中明确最优策略：
- Turn 1：所有READ并行（读MEMORY.md + daily notes）
- Turn 2：所有WRITE并行（更新MEMORY.md + LanceDB存储）

这比read/write交替执行更高效，减少token浪费。

## 与AutoDream整合的关系
- **Extract Memories**: 每次对话后，提取具体事实
- **Memory Maintenance（AutoDream风格）**: 定期整合daily notes到MEMORY.md
- 两者互补：实时细粒度提取 + 定期批量整合
