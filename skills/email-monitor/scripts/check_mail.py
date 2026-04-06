#!/usr/bin/env python3
"""
邮件监控脚本 - 支持 IMAP IDLE + 轮询兜底
监控邮箱，检测新邮件，总结内容，下载附件，推送到飞书
"""

import os
import sys
import json
import email
import imaplib
import ssl
import hashlib
import subprocess
import select
import socket
import time
import threading
import shutil
import urllib.parse
import requests
from email.header import decode_header, make_header
from email.utils import parseaddr
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "data"
LAST_CHECK_FILE = CONFIG_DIR / "last_check.json"
ATTACHMENTS_DIR = CONFIG_DIR / "attachments"

# 飞书配置
FEISHU_ACCOUNT = "main"
FEISHU_USER_ID = "ou_c5c98e2002a34a9b10f15fd0b6463d06"

# 监控配置
IDLE_TIMEOUT = 29 * 60  # IDLE 超时（29分钟，服务器通常30分钟）
POLL_INTERVAL = 300     # 轮询间隔（5分钟）
RECONNECT_DELAY = 30    # 重连延迟
MAX_RECONNECT = 0       # 最大重连次数（0=无限）
NOOP_INTERVAL = 120     # 心跳检测间隔（秒）

os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)


def load_env():
    """从 .env.email 文件加载环境变量"""
    env_paths = [
        Path(__file__).parent.parent.parent.parent / ".env.email",
        Path.home() / ".openclaw" / "workspace" / ".env.email",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key, value)
            return True
    return False


def get_config():
    """获取邮箱配置"""
    return {
        "imap_server": os.environ.get("EMAIL_IMAP_SERVER"),
        "imap_port": int(os.environ.get("EMAIL_IMAP_PORT", 993)),
        "smtp_server": os.environ.get("EMAIL_SMTP_SERVER"),
        "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", 465)),
        "user": os.environ.get("EMAIL_USER"),
        "password": os.environ.get("EMAIL_PASSWORD"),
    }


def decode_str(s):
    """解码邮件头字符串"""
    if s is None:
        return ""
    
    try:
        # 使用 make_header 自动处理 RFC 2047 编码
        decoded = str(make_header(decode_header(s)))
        return decoded
    except Exception:
        pass
    
    # 备用解码方式
    try:
        decoded_parts = decode_header(s)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)
    except Exception:
        return s if isinstance(s, str) else str(s)


def decode_filename(part):
    """解码附件文件名，支持多种编码方式"""
    filename = None
    
    # 尝试 filename* 参数 (RFC 2231)
    filename_param = part.get_param("filename*", header="Content-Disposition")
    if filename_param:
        try:
            # RFC 2231 格式: charset'language'encoded_filename
            if isinstance(filename_param, tuple):
                charset, language, encoded = filename_param
                filename = urllib.parse.unquote(encoded, encoding=charset or 'utf-8')
            else:
                filename = filename_param
        except Exception:
            pass
    
    # 尝试普通 filename 参数
    if not filename:
        filename = part.get_filename()
    
    if not filename:
        return None
    
    # 解码 RFC 2047 编码的文件名
    try:
        decoded = decode_str(filename)
        return decoded
    except Exception:
        return filename


def get_email_body(msg):
    """提取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            if "attachment" in content_disposition:
                continue
            
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    if content_type == "text/plain":
                        body = text
                        break
                    elif content_type == "text/html" and not body:
                        body = text
            except Exception:
                pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
        except Exception:
            pass
    
    return body.strip()


def save_attachments(msg, email_id):
    """保存邮件附件"""
    attachments = []
    email_dir = ATTACHMENTS_DIR / email_id
    os.makedirs(email_dir, exist_ok=True)
    
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in content_disposition:
            # 使用增强的文件名解码函数
            filename = decode_filename(part)
            if filename:
                # 清理文件名中的非法字符
                filename = "".join(c for c in filename if c not in r'<>:"/\|?*')
                filepath = email_dir / filename
                payload = part.get_payload(decode=True)
                if payload:
                    with open(filepath, "wb") as f:
                        f.write(payload)
                    attachments.append({
                        "filename": filename,
                        "path": str(filepath),
                        "size": len(payload)
                    })
    
    return attachments


def load_last_check():
    """加载上次检查状态"""
    if LAST_CHECK_FILE.exists():
        try:
            with open(LAST_CHECK_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_uid": 0, "processed_ids": []}


def save_last_check(data):
    """保存检查状态（原子写入）"""
    import tempfile
    temp_file = LAST_CHECK_FILE.with_suffix('.tmp')
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)
    temp_file.replace(LAST_CHECK_FILE)  # 原子操作


class EmailMonitor:
    """邮件监控类 - 支持 IDLE + 轮询"""
    
    def __init__(self, config):
        self.config = config
        self.mail = None
        state = load_last_check()
        self.last_uid = int(state.get("last_uid", 0))
        self.processed = set(state.get("processed_ids", []))
        self.running = True
        self.last_poll_time = 0
        self.last_noop_time = 0
        self.reconnect_count = 0

    def is_connected(self):
        """检查连接是否存活（NOOP 心跳）"""
        if not self.mail:
            return False
        try:
            status, _ = self.mail.noop()
            if status != "OK":
                return False
            self.last_noop_time = time.time()
            return True
        except Exception:
            return False

    def ensure_connected(self):
        """确保连接可用，断开则自动重连。返回 True=可用"""
        if self.mail and time.time() - self.last_noop_time < NOOP_INTERVAL:
            # 最近心跳正常，跳过检查
            return True

        if self.is_connected():
            return True

        # 连接已断开，尝试重连
        print("连接已断开，正在重连...", file=sys.stderr)
        self.disconnect()
        return self.connect()

    def connect(self):
        """连接到 IMAP 服务器（支持重试）"""
        last_error = None
        for attempt in range(3):
            try:
                ssl_context = ssl.create_default_context()
                # 酒钢邮箱可能使用较旧的 TLS，放宽协议限制
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                self.mail = imaplib.IMAP4_SSL(
                    self.config["imap_server"],
                    self.config["imap_port"],
                    ssl_context=ssl_context,
                    timeout=30
                )
                self.mail.login(self.config["user"], self.config["password"])
                self.mail.select("INBOX")
                self.last_noop_time = time.time()
                self.reconnect_count += 1
                print(f"已连接到 {self.config['imap_server']} (第{self.reconnect_count}次)", file=sys.stderr)
                return True
            except (ssl.SSLError, socket.error, OSError, imaplib.IMAP4.abort) as e:
                last_error = e
                print(f"连接失败(第{attempt+1}次): {e}", file=sys.stderr)
                self.disconnect()
                time.sleep(min(5 * (attempt + 1), 30))
            except Exception as e:
                last_error = e
                print(f"连接异常: {e}", file=sys.stderr)
                self.disconnect()
                break

        print(f"连接彻底失败: {last_error}", file=sys.stderr)
        return False

    def disconnect(self):
        """安全断开连接"""
        try:
            if self.mail:
                try:
                    self.mail.noop()  # 先测试是否还活着
                except Exception:
                    pass
                try:
                    self.mail.logout()
                except Exception:
                    try:
                        self.mail.close()
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self.mail = None
    
    def check_new_emails(self):
        """检查新邮件（使用UID递增检测，高效且不重复）"""
        try:
            # 获取当前最大UID
            status, messages = self.mail.uid("search", None, "ALL")
            if status != "OK" or not messages[0]:
                return []
            
            all_uids = [int(uid) for uid in messages[0].split()]
            current_max_uid = max(all_uids) if all_uids else 0
            
            # 首次运行，记录当前最大UID，不推送历史邮件
            if self.last_uid == 0:
                self.last_uid = current_max_uid
                save_last_check({
                    "last_uid": self.last_uid,
                    "processed_ids": list(self.processed)
                })
                print(f"首次运行，记录当前UID: {self.last_uid}", file=sys.stderr)
                return []
            
            # 查询UID大于上次记录的邮件
            if current_max_uid <= self.last_uid:
                return []
            
            # 搜索新邮件（UID范围语法：直接使用数字，不需要UID前缀）
            status, messages = self.mail.uid("search", None, f"{self.last_uid + 1}:*")
            if status != "OK" or not messages[0]:
                return []
            
            new_uids = messages[0].split()
            if not new_uids:
                return []
            
            print(f"发现 {len(new_uids)} 封新邮件 (UID > {self.last_uid})", file=sys.stderr)
            
            new_emails = []
            max_processed_uid = self.last_uid
            
            for uid_bytes in new_uids:
                uid = int(uid_bytes)
                uid_str = uid_bytes.decode()
                
                # 只获取头部信息（快速）
                status, msg_data = self.mail.uid("fetch", uid_bytes, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                
                header_raw = msg_data[0][1]
                msg_header = email.message_from_bytes(header_raw)
                
                subject = decode_str(msg_header.get("Subject", ""))
                from_addr = decode_str(msg_header.get("From", ""))
                date = msg_header.get("Date", "")
                message_id = msg_header.get("Message-ID", "")
                
                email_hash = hashlib.md5(f"{message_id}{from_addr}{subject}".encode()).hexdigest()[:12]
                
                # 双重检查（UID + 哈希）
                if email_hash in self.processed:
                    max_processed_uid = max(max_processed_uid, uid)
                    continue
                
                print(f"处理新邮件: {subject[:40]}...", file=sys.stderr)
                
                new_emails.append({
                    "id": email_hash,
                    "email_id": uid_str,
                    "subject": subject,
                    "from": from_addr,
                    "date": date,
                    "body": "",  # 先不获取正文，避免超时
                    "attachments": []
                })
                
                self.processed.add(email_hash)
                max_processed_uid = max(max_processed_uid, uid)
            
            # 更新最大UID（先保存，确保不漏）
            self.last_uid = max(current_max_uid, max_processed_uid)
            save_last_check({
                "last_uid": self.last_uid,
                "processed_ids": list(self.processed)[-500:]
            })
            
            # 然后再获取附件（可选，失败不影响通知）
            for email_data in new_emails:
                try:
                    uid_bytes = email_data["email_id"].encode()
                    status, msg_data = self.mail.uid("fetch", uid_bytes, "(RFC822)")
                    if status == "OK" and msg_data and msg_data[0]:
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        email_data["body"] = get_email_body(msg)[:2000]
                        email_data["attachments"] = save_attachments(msg, email_data["id"])
                except Exception as e:
                    print(f"获取邮件详情失败: {e}", file=sys.stderr)
            
            return new_emails
            
        except (ssl.SSLError, socket.error, OSError, ConnectionResetError, imaplib.IMAP4.abort) as e:
            # 连接级错误，必须重连
            raise
        except Exception as e:
            print(f"检查邮件失败: {e}", file=sys.stderr)
            return []
    
    def idle(self):
        """进入 IDLE 模式等待新邮件"""
        try:
            # 发送 IDLE 命令
            self.mail.send(b'IDLE\r\n')
            response = self.mail.readline()
            
            if b'+ idling' not in response.lower() and b'+ OK' not in response.lower():
                print(f"IDLE 不受支持，将使用轮询模式", file=sys.stderr)
                return False
            
            print("进入 IDLE 模式，等待新邮件...", file=sys.stderr)
            
            # 等待服务器通知或超时
            socket_obj = self.mail.socket()
            socket_obj.setblocking(0)
            
            start_time = time.time()
            
            while self.running:
                elapsed = time.time() - start_time
                
                # 超时检查
                if elapsed >= IDLE_TIMEOUT:
                    print("IDLE 超时，重新进入...", file=sys.stderr)
                    break
                
                # 轮询兜底检查（每 POLL_INTERVAL 秒）
                if elapsed - self.last_poll_time >= POLL_INTERVAL:
                    self.last_poll_time = elapsed
                    # 退出 IDLE 进行轮询检查
                    self.mail.send(b'DONE\r\n')
                    self.mail.readline()  # 读取 OK 响应
                    
                    # 检查新邮件
                    new_emails = self.check_new_emails()
                    if new_emails:
                        self.process_emails(new_emails)
                    
                    # 重新进入 IDLE
                    self.mail.send(b'IDLE\r\n')
                    self.mail.readline()
                    continue
                
                # 检查是否有数据可读（服务器通知）
                try:
                    ready, _, _ = select.select([socket_obj], [], [], 10)
                    if ready:
                        response = self.mail.readline()
                        if response:
                            # 收到新邮件通知
                            if b'EXISTS' in response or b'RECENT' in response:
                                print(f"收到新邮件通知: {response.decode().strip()}", file=sys.stderr)
                                
                                # 退出 IDLE
                                self.mail.send(b'DONE\r\n')
                                self.mail.readline()
                                
                                # 检查新邮件
                                new_emails = self.check_new_emails()
                                if new_emails:
                                    self.process_emails(new_emails)
                                
                                # 重新进入 IDLE
                                self.mail.send(b'IDLE\r\n')
                                self.mail.readline()
                                start_time = time.time()  # 重置超时计时器
                except (select.error, OSError):
                    # Socket 错误，可能连接断开
                    print("连接中断，准备重连...", file=sys.stderr)
                    return False
            
            # 正常退出 IDLE
            self.mail.send(b'DONE\r\n')
            self.mail.readline()
            return True
            
        except (ssl.SSLError, socket.error, OSError, ConnectionResetError, imaplib.IMAP4.abort) as e:
            print(f"IDLE 连接断开: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"IDLE 错误: {e}", file=sys.stderr)
            return False
    
    def poll_loop(self, max_iterations=1):
        """单次或多次轮询，遇到连接问题返回 False"""
        for _ in range(max_iterations):
            if not self.running:
                return True

            # 每次操作前检查连接
            if not self.ensure_connected():
                return False

            try:
                new_emails = self.check_new_emails()
                if new_emails:
                    self.process_emails(new_emails)
            except (ssl.SSLError, socket.error, OSError, imaplib.IMAP4.abort, ConnectionResetError) as e:
                print(f"连接异常: {e}，需要重连", file=sys.stderr)
                self.disconnect()
                return False
            except Exception as e:
                print(f"轮询错误: {e}", file=sys.stderr)
                # 非连接错误，可能是临时问题，不断开
                pass

            if max_iterations <= 1:
                break
            time.sleep(POLL_INTERVAL)

        return True
    
    def process_emails(self, emails):
        """处理新邮件"""
        for email_data in emails:
            summary = self.summarize_email(email_data)
            
            if notify_feishu(summary):
                print(f"已推送: {email_data['subject']}", file=sys.stderr)
            else:
                print(f"推送失败: {email_data['subject']}", file=sys.stderr)
            
            # 发送附件
            for att in email_data.get("attachments", []):
                send_attachment(att)
    
    def summarize_email(self, email_data):
        """总结邮件内容"""
        subject = email_data.get("subject", "无主题")
        from_addr = email_data.get("from", "未知发件人")
        body = email_data.get("body", "")
        
        summary = f"📧 新邮件通知\n\n"
        summary += f"发件人：{from_addr}\n"
        summary += f"主题：{subject}\n"
        summary += f"时间：{email_data.get('date', '未知')}\n\n"
        
        if body:
            preview = body[:200].replace("\n", " ").strip()
            summary += f"内容预览：{preview}...\n"
        
        attachments = email_data.get("attachments", [])
        if attachments:
            summary += f"\n📎 附件 ({len(attachments)}个)：\n"
            for att in attachments:
                size_kb = att["size"] / 1024
                summary += f"  • {att['filename']} ({size_kb:.1f}KB)\n"
        
        return summary
    
    def run(self):
        """运行监控 - 统一连接管理，自动重连"""
        print(f"邮件监控启动: {self.config['user']}", file=sys.stderr)
        print(f"模式: IDLE(优先) + 轮询兜底 | 心跳: {NOOP_INTERVAL}s | 重连延迟: {RECONNECT_DELAY}s", file=sys.stderr)

        while self.running:
            # 1. 建立连接（失败则等待重试）
            if not self.connect():
                if MAX_RECONNECT > 0 and self.reconnect_count >= MAX_RECONNECT:
                    print("达到最大重连次数，退出", file=sys.stderr)
                    break
                print(f"{RECONNECT_DELAY}秒后重连...", file=sys.stderr)
                for _ in range(RECONNECT_DELAY):
                    if not self.running:
                        break
                    time.sleep(1)
                continue

            # 2. 尝试 IDLE 模式
            try:
                idle_ok = self.idle()
                if idle_ok:
                    # IDLE 正常退出（超时），回到外层循环重新连接（刷新连接）
                    self.disconnect()
                    continue
            except Exception as e:
                print(f"IDLE 异常: {e}", file=sys.stderr)
                self.disconnect()

            # 3. IDLE 不可用，进入轮询模式
            print(f"使用轮询模式（每 {POLL_INTERVAL} 秒检查一次）...", file=sys.stderr)

            while self.running:
                ok = self.poll_loop(max_iterations=1)
                if not ok:
                    # 连接断开，回到外层重连
                    print(f"轮询检测到断连，回到重连循环", file=sys.stderr)
                    break
                time.sleep(POLL_INTERVAL)

            self.disconnect()
            if self.running:
                print(f"等待 {RECONNECT_DELAY}s 后重连...", file=sys.stderr)
                time.sleep(RECONNECT_DELAY)


def notify_feishu(summary):
    """推送到飞书"""
    try:
        result = subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", "feishu",
                "--account", FEISHU_ACCOUNT,
                "-t", f"user:{FEISHU_USER_ID}",
                "-m", summary
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"飞书推送失败: {result.stderr}", file=sys.stderr)
            return False
        print(f"飞书推送成功", file=sys.stderr)
        return True
    except Exception as e:
        print(f"飞书推送失败: {e}", file=sys.stderr)
        return False


def add_to_knowledge_base(att_path, att_filename):
    """将附件存入知识库"""
    try:
        # 调用知识库脚本添加文件
        kb_script = str(Path.home() / ".openclaw" / "workspace" / "skills" / "knowledge-base" / "scripts" / "kb_manager.py")
        workspace_dir = str(Path.home() / ".openclaw" / "workspace")
        
        if not os.path.exists(kb_script):
            print(f"知识库脚本不存在: {kb_script}", file=sys.stderr)
            return False
        
        result = subprocess.run(
            ["python3", kb_script, "add", att_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=workspace_dir
        )
        
        if result.returncode == 0:
            print(f"✅ 已存入知识库: {att_filename}", file=sys.stderr)
            notify_feishu(f"📚 已将 {att_filename} 存入知识库 ✅")
            return True
        else:
            print(f"存入知识库失败: {result.stderr}", file=sys.stderr)
            notify_feishu(f"⚠️ 知识库入库失败: {att_filename}")
            return False
    except Exception as e:
        print(f"存入知识库异常: {e}", file=sys.stderr)
        notify_feishu(f"⚠️ 知识库入库异常: {att_filename}")
        return False


def send_attachment(att):
    """发送附件到飞书（使用飞书 API 上传文件）并自动存入知识库"""
    import requests

    att_path = att.get("path", "")
    att_filename = att.get("filename", "attachment")
    if not att_path or not os.path.exists(att_path):
        return False

    try:
        # 先发送文件名提示
        notify_feishu(f"📎 附件：{att_filename}\n📚 正在存入知识库...")

        # 自动存入知识库（异步执行，不阻塞邮件处理）
        kb_thread = threading.Thread(
            target=add_to_knowledge_base,
            args=(att_path, att_filename),
            daemon=True
        )
        kb_thread.start()

        # 获取飞书 tenant_access_token
        feishu_config = get_feishu_config()
        if not feishu_config:
            print("飞书配置不存在", file=sys.stderr)
            return False

        token = get_feishu_token(feishu_config)
        if not token:
            print("获取飞书 token 失败", file=sys.stderr)
            return False

        # 上传文件到飞书
        with open(att_path, "rb") as f:
            file_content = f.read()

        upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        files = {
            "file": (att_filename, file_content),
            "file_type": (None, "stream"),
        }
        data = {
            "file_type": "stream",
            "file_name": att_filename,
        }

        response = requests.post(
            upload_url,
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )

        if response.status_code != 200:
            print(f"上传文件失败: {response.status_code} {response.text}", file=sys.stderr)
            return False

        result = response.json()
        if result.get("code") != 0:
            print(f"上传文件失败: {result}", file=sys.stderr)
            return False

        file_key = result["data"]["file_key"]

        # 发送文件消息（使用 open_id）
        send_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        send_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        send_data = {
            "receive_id": FEISHU_USER_ID,
            "msg_type": "file",
            "content": json.dumps({"file_key": file_key})
        }

        response = requests.post(
            send_url,
            headers=send_headers,
            json=send_data,
            timeout=30
        )

        if response.status_code != 200:
            print(f"发送文件消息失败: {response.status_code} {response.text}", file=sys.stderr)
            return False

        result = response.json()
        if result.get("code") != 0:
            print(f"发送文件消息失败: {result}", file=sys.stderr)
            return False

        print(f"附件发送成功: {att_filename}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"附件发送失败 {att_filename}: {e}", file=sys.stderr)
        return False


def get_feishu_config():
    """获取飞书配置"""
    try:
        config_path = Path("/root/.openclaw/openclaw.json")
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            config = json.load(f)

        feishu_accounts = config.get("channels", {}).get("feishu", {}).get("accounts", {})
        main_account = feishu_accounts.get("main", {})

        return {
            "app_id": main_account.get("appId"),
            "app_secret": main_account.get("appSecret")
        }
    except Exception as e:
        print(f"读取飞书配置失败: {e}", file=sys.stderr)
        return None


def get_feishu_token(config):
    """获取飞书 tenant_access_token"""
    import requests

    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": config["app_id"],
            "app_secret": config["app_secret"]
        }

        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        if result.get("code") != 0:
            print(f"获取 token 失败: {result}", file=sys.stderr)
            return None

        return result.get("tenant_access_token")
    except Exception as e:
        print(f"获取 token 失败: {e}", file=sys.stderr)
        return None


def check_once():
    """单次检查模式（用于 cron）"""
    # 使用文件锁防止多个实例同时运行
    import fcntl
    lock_file = CONFIG_DIR / "check.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # 另一个实例正在运行
        print("另一个检查实例正在运行，跳过", file=sys.stderr)
        return
    
    try:
        if not load_env():
            print("错误: 无法加载邮箱配置", file=sys.stderr)
            return
        
        config = get_config()
        
        if not all([config["imap_server"], config["user"], config["password"]]):
            print("错误: 邮箱配置不完整", file=sys.stderr)
            return
        
        monitor = EmailMonitor(config)
        if monitor.connect():
            new_emails = monitor.check_new_emails()
            if new_emails:
                print(f"发现 {len(new_emails)} 封新邮件", file=sys.stderr)
                monitor.process_emails(new_emails)
                print(json.dumps({
                    "new_count": len(new_emails),
                    "emails": [{"id": e["id"], "subject": e["subject"], "from": e["from"]} for e in new_emails]
                }, ensure_ascii=False, indent=2))
            else:
                print("没有新邮件", file=sys.stderr)
            monitor.disconnect()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def main():
    """主函数"""
    if not load_env():
        print("错误: 无法加载邮箱配置", file=sys.stderr)
        sys.exit(1)
    
    config = get_config()
    
    if not all([config["imap_server"], config["user"], config["password"]]):
        print("错误: 邮箱配置不完整", file=sys.stderr)
        sys.exit(1)
    
    # 检查是否是单次检查模式
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        check_once()
        return
    
    # 持续监控模式
    monitor = EmailMonitor(config)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\n监控已停止", file=sys.stderr)
        monitor.running = False
        monitor.disconnect()


if __name__ == "__main__":
    main()
