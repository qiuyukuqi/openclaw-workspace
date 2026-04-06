"""自动发布框架 - 全局配置"""
import os

# 各平台创作者后台URL
TOUTIAO_EDITOR_URL = "https://mp.toutiao.com/profile_v4/graphic/articles/new"
ZHIHU_EDITOR_URL = "https://zhuanlan.zhihu.com/write"
XIAOHONGSHU_CREATE_URL = "https://creator.xiaohongshu.com/publish/publish"

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# storage_state保存目录
AUTH_DIR = os.path.join(BASE_DIR, "auth")
# 临时截图目录
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 确保目录存在
for d in [AUTH_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# 默认超时（毫秒）
DEFAULT_TIMEOUT = 30000
# 默认导航超时
NAVIGATION_TIMEOUT = 60000
