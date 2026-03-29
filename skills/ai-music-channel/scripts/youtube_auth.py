#!/usr/bin/env python3
"""YouTube OAuth授权 - 获取并刷新token（修复版：避免from_authorized_user_file的文件清空bug）"""
import os, json, requests as http_requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/youtube.force-ssl']
TOKEN_FILE = os.path.expanduser('~/.openclaw/workspace/.youtube_token.json')
CLIENT_ID = "699372916971-jfi4f1qk3flu2j5sjgqaqm41rirj085r.apps.googleusercontent.com"
CLIENT_SECRET = "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"
TOKEN_URI = "https://oauth2.googleapis.com/token"

def _read_token():
    """Read token file safely, never corrupt it"""
    try:
        if os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 10:
            with open(TOKEN_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return None

def _write_token(data):
    """Write token file atomically"""
    tmp = TOKEN_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, TOKEN_FILE)

def _refresh_token(refresh_token):
    """Refresh access token using refresh_token directly via HTTP"""
    r = http_requests.post(TOKEN_URI, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }, timeout=20)
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Token refresh failed: {d}")
    return d["access_token"]

def get_credentials():
    """Get valid credentials, refreshing if needed"""
    data = _read_token()
    if not data or not data.get("refresh_token"):
        raise RuntimeError("YouTube token missing. Please re-authorize.")

    # Get fresh access token
    access_token = _refresh_token(data["refresh_token"])

    creds = Credentials(
        token=access_token,
        refresh_token=data["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES
    )
    return creds

def save_token_from_code(code, verifier):
    """Exchange authorization code for tokens and save"""
    r = http_requests.post(TOKEN_URI, data={
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "http://localhost:8080",
        "grant_type": "authorization_code",
        "code_verifier": verifier
    }, timeout=20)
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Code exchange failed: {d}")
    
    _write_token({
        "token": d["access_token"],
        "refresh_token": d.get("refresh_token"),
        "token_uri": TOKEN_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES
    })
    return d.get("refresh_token") is not None

def upload_video(file_path, title, description, tags, thumbnail=None):
    """Upload video to YouTube"""
    creds = get_credentials()
    yt = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if isinstance(tags, str) else tags,
            "categoryId": "10"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    
    request = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(file_path, resumable=True, chunksize=5*1024*1024)
    )
    
    response = None
    while response is None:
        _, response = request.next_chunk()
    
    return response["id"], f"https://www.youtube.com/watch?v={response['id']}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        # Usage: python youtube_auth.py save <code> <verifier>
        code = sys.argv[2]
        verifier = sys.argv[3]
        ok = save_token_from_code(code, verifier)
        print(f"Token saved! refresh_token: {ok}")
    else:
        creds = get_credentials()
        print("Token OK!")
