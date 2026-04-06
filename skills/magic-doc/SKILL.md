# /magic-doc — 自动维护文档技能（v2，源自Claude Code MagicDocs）

自动发现和更新带有特殊标记头的markdown文档。

## 使用场景
- 项目中有需要持续更新的设计文档、架构说明、配置指南
- 文档内容随代码演进需要同步更新

## 标记头格式

文档开头包含以下格式会被识别为Magic Doc：

```markdown
# MAGIC DOC: 文档标题
_描述：这个文档的用途_
_更新频率：每次相关代码变更时_
```

## 文档哲学（源自Claude Code）

**BE TERSE. High signal only.**
- 只记录WHY/HOW/WHERE，不记录详细代码步骤
- 每行entry保持≤150字符
- 这不是changelog，是当前状态的文档
- "Keep the document CURRENT" — 移除过时信息

## 模板变量安全（源自Claude Code）

使用`{{variable}}`语法，用单次正则替换：
```javascript
text.replace(/\{\{(\w+)\}\}/g, (_, key) => values[key])
```
⚠️ 禁止链式replace——会导致双重替换漏洞（用户内容包含`{{varName}}`时被错误替换）。

## 更新规则

1. **追加为主**：新信息追加到对应section，不删除旧内容
2. **冲突处理**：新旧信息矛盾时，新信息优先，标记旧信息为"已废弃"
3. **长度控制**：单个Magic Doc不超过500行
4. **索引维护**：每个条目一行：`- [Title](file.md) — one-line hook`

## 自定义Prompt
用户可在`~/.openclaw/workspace/magic-docs/prompt.md`覆盖默认模板（类似Claude Code的`~/.claude/magic-docs/prompt.md`）
