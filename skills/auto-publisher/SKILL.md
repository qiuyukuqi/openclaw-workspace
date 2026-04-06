# auto-publisher - 跨平台自动发布技能

将Markdown文章自动发布到头条号、知乎、小红书。

## 触发词
- "发布文章"、"自动发布"、"publish article"
- "发布到头条"、"发布到知乎"、"发布到小红书"
- "跨平台发布"、"一键发布"

## 使用方式

### 发布文章
提供Markdown文件路径和标题，指定目标平台：
```
发布文章到头条号，标题是"xxx"，内容文件是 /path/to/article.md
发布到知乎专栏，标题"xxx"，内容 /path/to/article.md
发布到小红书，标题"xxx"，内容 /path/to/note.md，封面图 /path/to/cover.jpg
```

### 登录平台（需要用户在有GUI的电脑操作）
```
帮我登录头条号
需要重新登录知乎
```

### 测试登录状态
```
测试一下头条号的登录状态
检查小红书cookie是否过期
```

## 命令参考

```bash
# 登录（有GUI电脑）
python ~/.openclaw/workspace/skills/auto-publisher/publisher.py login <platform>

# 发布
python ~/.openclaw/workspace/skills/auto-publisher/publisher.py publish <platform> \
  --title "标题" --content /path/to/article.md [--cover /path/to/cover.jpg] \
  [--question-url "https://zhihu.com/question/xxx"] [--tags "#tag1" "#tag2"]

# 测试
python ~/.openclaw/workspace/skills/auto-publisher/publisher.py test <platform>
```

## 平台参数
- `toutiao` - 头条号
- `zhihu` - 知乎（专栏模式默认，加 `--question-url` 为回答模式）
- `xiaohongshu` - 小红书

## 注意事项
- 服务器是headless模式，登录需在用户电脑操作后上传state文件
- 小红书必须上传图片
- Cookie会过期，需定期检查
