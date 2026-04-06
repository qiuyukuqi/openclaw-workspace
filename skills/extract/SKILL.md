# /extract — 对话后记忆提取技能

参考Claude Code的Extract Memories机制，在重要对话结束后，提取本次对话中遗漏或值得长期记住的信息。

## 使用场景
- 完成一个复杂任务后（发布流水线、系统配置、问题排查）
- 学到新知识/踩到新坑后
- 用户明确要求"记住这个"时
- heartbeat轮换检查时

## 触发条件

满足以下任一条件即触发：
1. 本次对话产生了新的工具命令/脚本/配置
2. 本次对话修复了bug或解决了问题
3. 用户说了"记住"、"记一下"
4. 距上次提取超过24小时且有非trivial对话

## 提取流程

### Step 1: 回顾本次对话
- 浏览对话历史中的关键决策、错误、解决方案
- 识别值得长期保存的信息

### Step 2: 分类存储

按类型存入对应位置：

| 信息类型 | 存储位置 | 格式 |
|---------|---------|------|
| 规则/铁律 | MEMORY.md 铁律section | Rule格式 |
| 错误修复 | MEMORY.md 错误与修复section | 问题→修复格式 |
| 工作流 | MEMORY.md 工作流section | 命令/步骤格式 |
| 项目信息 | MEMORY.md 关键项目section | 表格格式 |
| 通用知识 | MEMORY.md 通用知识section | 要点格式 |
| 快速检索 | LanceDB memory_store | 原子化条目 |

### Step 3: 去重验证
- 检查MEMORY.md是否已有类似内容（避免重复）
- 如果更新已有条目，标注更新日期
- 重要条目同时存LanceDB（用memory_recall验证可检索）

### Step 4: 更新Current State
- 更新MEMORY.md的Current State section
- 反映最新的工作状态和下一步计划

## 与AutoDream整合的关系
- **Extract Memories**: 每次对话后，提取具体事实
- **Memory Maintenance（AutoDream风格）**: 定期整合daily notes到MEMORY.md
- 两者互补：一个是实时细粒度提取，一个是定期批量整合
