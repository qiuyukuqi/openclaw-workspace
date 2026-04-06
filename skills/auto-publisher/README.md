# auto-publisher

跨平台自动发布框架：**公众号文章 → AI改编 → 一键发布到头条号/小红书/知乎**

## 完整流程

```
公众号文章URL → 读取内容 → AI改编为各平台版本 → Playwright自动发布
```

## 架构

```
auto-publisher/
├── publisher.py              # CLI统一入口
├── config.py                 # 配置
├── core/
│   ├── base.py               # BasePublisher基类
│   ├── login_manager.py      # Cookie登录管理（持久化context）
│   ├── markdown_converter.py # Markdown转换
│   ├── notifier.py           # 飞书通知
│   └── wechat_reader.py      # 公众号文章读取器
├── platforms/
│   ├── toutiao.py            # 头条号发布器（✅ 已测试通过）
│   ├── xiaohongshu.py        # 小红书发布器
│   └── zhihu.py              # 知乎发布器（⚠️ 反自动化限制）
├── scripts/
│   └── toutiao_publish.py    # 头条独立发布脚本（可直接调用）
└── auth/                     # 登录状态
```

## 各平台状态

| 平台 | 状态 | Cookie来源 | 说明 |
|------|------|-----------|------|
| 头条号 | ✅ 可用 | Windows服务器导出 | save=1直接提交审核 |
| 小红书 | ⏳ 待测试 | Windows持久化context | 代码已完善 |
| 知乎 | ❌ 受限 | Windows导出 | 反自动化检测拦截 |

## 使用方式

### 1. 发布到头条号

```bash
# 独立脚本（推荐，已测试通过）
python3 scripts/toutiao_publish.py --title "标题" --content "正文" --cover cover.jpg

# 或通过CLI入口
python3 publisher.py publish toutiao --title "标题" --content article.md --cover cover.jpg
```

### 2. 读取公众号文章

```bash
python3 -c "
from core.wechat_reader import fetch_wechat_article
article = fetch_wechat_article('https://mp.weixin.qq.com/s/xxx')
print(article['title'])
print(article['content_markdown'])
"
```

### 3. Cookie管理

头条号cookie导出（从Windows服务器）：
```bash
# 在Windows服务器上运行
python export_all.py toutiao

# 拉到本地
scp Administrator@43.135.179.141:.../toutiao_storage_state.json /tmp/openclaw/toutiao_cookies.json
```

## 注意事项

- 头条号的save=1 = 发布/提交审核，没有"仅保存草稿"选项
- 知乎反自动化检测很强，需要真人过安全验证
- 小红书必须上传图片才能发布
