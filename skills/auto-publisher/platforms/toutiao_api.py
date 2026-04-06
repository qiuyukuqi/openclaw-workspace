"""头条号发布器 - 使用内部API直接发布（不需要浏览器）"""
import os
import json
import requests
from core.base import BasePublisher
from core.markdown_converter import md_to_html
from core.notifier import notify_success, notify_failure


class ToutiaoPublisher(BasePublisher):
    """今日头条号文章发布器 - API版"""

    def __init__(self):
        super().__init__("toutiao")
        self.session = requests.Session()
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Referer": "https://mp.toutiao.com/profile_v4/graphic/articles/new",
            "Origin": "https://mp.toutiao.com",
        }

    async def setup(self, headless: bool = True):
        """从持久化目录读取cookie"""
        # Cookie文件路径
        cookie_file = os.path.join("auth", "toutiao_data", "cookies.json")
        
        if os.path.exists(cookie_file):
            with open(cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            for cookie in cookies:
                self.session.cookies.set(
                    cookie["name"], cookie["value"],
                    domain=cookie.get("domain", ".toutiao.com")
                )
            print(f"[{self.platform_name}] 已加载 {len(cookies)} 个cookie")
        else:
            # 尝试从Playwright持久化目录的storage读取
            storage_file = os.path.join("auth", "toutiao_data", "storage_state.json")
            if os.path.exists(storage_file):
                with open(storage_file, "r", encoding="utf-8") as f:
                    storage = json.load(f)
                for cookie in storage.get("cookies", []):
                    self.session.cookies.set(
                        cookie["name"], cookie["value"],
                        domain=cookie.get("domain", ".toutiao.com")
                    )
                print(f"[{self.platform_name}] 已从storage_state加载cookie")
            else:
                raise RuntimeError("未找到登录cookie，请先运行: python publisher.py login toutiao")

        # 验证登录状态
        self._check_login()

    async def close(self):
        """API版不需要关闭浏览器"""
        self.session.close()

    def _check_login(self):
        """验证登录状态"""
        resp = self.session.get(
            "https://mp.toutiao.com/mp/agw/media/user_login_status_api",
            headers=self.base_headers,
            timeout=10
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"登录状态无效: {data.get('message', '未知错误')}")
        print(f"[{self.platform_name}] ✅ 登录验证通过")

    def _get_signature(self):
        """获取_signature参数（从页面JS中提取）"""
        # 先访问编辑器页面获取页面中的签名参数
        resp = self.session.get(
            "https://mp.toutiao.com/profile_v4/graphic/articles/new",
            headers=self.base_headers,
            timeout=15
        )
        html = resp.text
        # 尝试从页面中提取__ac_signature或__ac_nonce
        import re
        sig_match = re.search(r"__ac_signature=([^\"'&\s]+)", html)
        nonce_match = re.search(r"__ac_nonce=([^\"'&\s]+)", html)
        return sig_match.group(1) if sig_match else "", nonce_match.group(1) if nonce_match else ""

    def _upload_image(self, image_path: str) -> str:
        """上传图片，返回图片URL
        
        Returns:
            上传后的图片URL或web_uri
        """
        abs_path = os.path.abspath(image_path)
        upload_url = "https://mp.toutiao.com/mp/agw/article_material/photo/upload_picture"
        params = {
            "type": "ueditor",
            "pgc_watermark": "0",
            "action": "uploadimage",
            "encode": "utf-8",
            "is_private": "0",
        }
        headers = {**self.base_headers, "Accept": "application/json"}
        
        with open(abs_path, "rb") as f:
            files = {"upfile": (os.path.basename(abs_path), f, "image/jpeg")}
            resp = self.session.post(
                upload_url, params=params, headers=headers,
                files=files, timeout=30
            )
        
        result = resp.json()
        print(f"[{self.platform_name}] 图片上传结果: {json.dumps(result, ensure_ascii=False)[:200]}")
        
        if result.get("code") == 0:
            data = result.get("data", {})
            return data.get("web_uri", "") or data.get("url", "")
        else:
            print(f"[{self.platform_name}] ⚠️ 图片上传失败: {result}")
            return ""

    async def publish(self, title: str, content: str, cover_image: str = None, **kwargs) -> bool:
        try:
            # 1. 获取签名
            print(f"[{self.platform_name}] 获取签名...")
            signature, nonce = self._get_signature()
            print(f"[{self.platform_name}] signature: {signature[:20]}... nonce: {nonce}")

            # 2. 上传封面图
            cover_web_uri = ""
            if cover_image and os.path.exists(cover_image):
                print(f"[{self.platform_name}] 上传封面图...")
                cover_web_uri = self._upload_image(cover_image)

            # 3. 构建文章内容
            html_content = md_to_html(content)
            
            # 4. 发布文章
            print(f"[{self.platform_name}] 发布文章: {title[:30]}...")
            
            publish_url = "https://mp.toutiao.com/mp/agw/article/wtt_article/publish"
            params = {"_signature": signature}
            
            article_data = {
                "title": title,
                "content": html_content,
                "article_type": "article",
                "pgc_info": {
                    "article_type": "article",
                    "title": title,
                    "content": html_content,
                },
                "resource_type": "article",
            }
            
            if cover_web_uri:
                article_data["pgc_info"]["web_uri"] = cover_web_uri
                article_data["cover_image_web_uri"] = cover_web_uri

            headers = {
                **self.base_headers,
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }
            
            # 尝试多个可能的API端点
            api_endpoints = [
                "https://mp.toutiao.com/mp/agw/article/wtt_article/publish",
                "https://mp.toutiao.com/mp/agw/article/publish",
                "https://mp.toutiao.com/mp/agw/content/article/publish",
            ]
            
            result = None
            last_resp = None
            for endpoint in api_endpoints:
                try:
                    params = {}
                    if signature:
                        params["_signature"] = signature
                    
                    resp = self.session.post(
                        endpoint,
                        params=params,
                        headers=headers,
                        data=json.dumps(article_data, ensure_ascii=False).encode("utf-8"),
                        timeout=30
                    )
                    last_resp = resp
                    print(f"[{self.platform_name}] {endpoint}: status={resp.status_code}")
                    
                    if resp.status_code == 200:
                        try:
                            result = json.loads(resp.text)
                            print(f"[{self.platform_name}] 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                        except:
                            print(f"[{self.platform_name}] 响应非JSON: {resp.text[:200]}")
                            continue
                        
                        if result.get("code") == 0 or result.get("data"):
                            break
                        else:
                            print(f"[{self.platform_name}] 错误: {json.dumps(result, ensure_ascii=False)[:300]}")
                except Exception as e:
                    print(f"[{self.platform_name}] {endpoint} failed: {e}")
                    continue
            
            if result and result.get("code") == 0:
                article_id = result.get("data", {}).get("item_id", "")
                notify_success(self.platform_name, f"{title} (ID: {article_id})", "")
                print(f"[{self.platform_name}] ✅ 发布成功！ID: {article_id}")
                return True
            else:
                error_msg = result.get("message", "未知错误")
                notify_failure(self.platform_name, error_msg, "")
                print(f"[{self.platform_name}] ❌ 发布失败: {error_msg}")
                return False

        except Exception as e:
            print(f"[{self.platform_name}] ❌ 发布失败: {e}")
            import traceback
            traceback.print_exc()
            notify_failure(self.platform_name, str(e), "")
            return False

    # 以下方法不需要了（API版），但保留接口兼容
    async def screenshot(self, name: str) -> str:
        return ""

    async def random_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        pass
