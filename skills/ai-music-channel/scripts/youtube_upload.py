#!/usr/bin/env python3
"""YouTube上传脚本"""
import os, sys, json, argparse
from youtube_auth import get_credentials
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build

def upload_video(file_path, title, description="", tags=None, thumbnail_path=None):
    creds = get_credentials()
    youtube = build('youtube', 'v3', credentials=creds)
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': '10'  # Music
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
            'embeddable': True
        }
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    
    response = None
    while response is None:
        _, response = request.next_chunk()
        if response:
            print(f"上传进度: {int(response.get('progress', 100))}%")
    
    video_id = response['id']
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"视频已上传: {video_url}")
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()
        print("缩略图已设置")
    
    return video_id, video_url

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--description', default='')
    parser.add_argument('--tags', nargs='+', default=[])
    parser.add_argument('--thumbnail', default=None)
    parser.add_argument('--playlist', default=None, help='Playlist ID to add video to')
    args = parser.parse_args()
    
    vid, url = upload_video(args.file, args.title, args.description, args.tags, args.thumbnail)
    
    if args.playlist:
        from youtube_auth import get_credentials
        from googleapiclient.discovery import build
        yt = build('youtube', 'v3', credentials=get_credentials())
        yt.playlistItems().insert(
            part='snippet',
            body={
                'snippet': {
                    'playlistId': args.playlist,
                    'resourceId': {'kind': 'youtube#video', 'videoId': vid}
                }
            }
        ).execute()
        print(f"已添加到播放列表: {args.playlist}")
    
    print(json.dumps({"video_id": vid, "url": url}))
