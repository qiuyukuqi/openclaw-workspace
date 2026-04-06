# HEARTBEAT.md

## 每次心跳检查

1. **检查邮件**（白天7:00-23:00）: 有无紧急未读邮件
2. **检查日程**: 未来2小时有无即将开始的事件

## 轮换检查（每次选1-2项，避免token浪费）

- [ ] 记忆维护：检查近期memory/YYYY-MM-DD.md，整合重要内容到MEMORY.md
- [ ] 记忆提取（/extract）：检查本次对话是否有遗漏的重要信息
- [ ] 代码审查：检查最近git diff，用/simplify审查
- [ ] 检查定时任务是否正常运行
- [ ] 天气（如用户可能外出）
- [ ] GitHub仓库状态（未push的commit）
- [ ] Magic Docs：检查MAGIC DOC标记的文档是否需要更新
- [ ] 进程健康（/stuck）：检查有无异常进程

## 记忆整合规则（参考AutoDream 4阶段模式）

当执行记忆维护时：
1. **Orient**: 扫描memory/目录，读取MEMORY.md当前内容
2. **Gather**: 读取近3天的daily notes，识别新的重要信息
3. **Consolidate**: 合并到MEMORY.md对应section（Current State/Errors/Key Projects等）
4. **Prune**: 移除过时信息，精简超长section（单section超30行需精简）
