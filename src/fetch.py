"""
用户视频列表获取模块
支持 API 和页面解析两种方式
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Callable, Optional

import requests

from src.config import COOKIES_FILE, VIDEO_LIST_FILE, SCRIPT_DIR


class VideoFetcher:
    """用户视频列表获取器"""

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        self.log_callback = log_callback
        self.progress_callback = progress_callback

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _progress(self, value: float, status: str = ""):
        if self.progress_callback:
            self.progress_callback(value, status)

    def _load_cookies(self) -> Dict[str, str]:
        """加载小红书 Cookie"""
        cookies = {}
        if COOKIES_FILE.exists():
            with open(COOKIES_FILE) as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
        return cookies

    def _get_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_user_videos(self, user_url: str, output_file: str = None, page_size: int = 10) -> dict:
        """获取小红书用户主页的视频链接（支持分页）"""
        self._log("=" * 50)
        self._log(f"[获取] 开始获取用户视频列表（每页{page_size}条）...")
        self._log("=" * 50)
        self._progress(0, "解析用户信息...")

        user_id_match = re.search(r'user/profile/([a-f0-9]+)', user_url)
        if not user_id_match:
            raise ValueError(f"无法从 URL 解析用户标识: {user_url}")

        sec_user_id = user_id_match.group(1)
        self._log(f"[获取] 用户标识: {sec_user_id}")

        cookies = self._load_cookies()
        self._log(f"[获取] 已加载 {len(cookies)} 个 Cookie")

        headers = self._get_headers()

        # 获取真实 user_id
        self._progress(10, "获取用户信息...")
        page_url = f"https://www.xiaohongshu.com/user/profile/{sec_user_id}"
        resp = requests.get(page_url, cookies=cookies, headers=headers, timeout=30)

        start_marker = 'window.__INITIAL_STATE__='
        start_idx = resp.text.find(start_marker)
        user_id = sec_user_id

        if start_idx != -1:
            json_start = start_idx + len(start_marker)
            json_text = resp.text[json_start:]
            json_text = json_text.replace(':undefined', ':null').replace(',undefined', ',null')

            decoder = json.JSONDecoder()
            try:
                state, _ = decoder.raw_decode(json_text)
                if 'user' in state and 'userInfo' in state['user']:
                    user_info = state['user']['userInfo']
                    if isinstance(user_info, dict) and 'userId' in user_info:
                        user_id = user_info['userId']
                        self._log(f"[获取] 真实用户 ID: {user_id}")
            except json.JSONDecodeError:
                pass

        videos = []
        cursor = ""
        page_num = 1

        api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted"

        api_headers = {
            **headers,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://www.xiaohongshu.com",
            "Referer": f"https://www.xiaohongshu.com/user/profile/{sec_user_id}",
        }

        while True:
            self._progress(10 + min(page_num * 20, 80), f"获取第 {page_num} 页...")

            params = {
                "user_id": user_id,
                "cursor": cursor,
                "num": page_size,
                "image_formats": "jpg,webp,avif",
                "xsec_token": "",
                "xsec_source": ""
            }

            self._log(f"[调试] 第 {page_num} 页请求参数: user_id={user_id}, cursor={cursor}, num={page_size}")

            try:
                api_resp = requests.get(api_url, params=params, cookies=cookies, headers=api_headers, timeout=30)
                data = api_resp.json()

                self._log(f"[调试] API 响应: code={data.get('code')}, msg={data.get('msg', 'N/A')}")
                resp_str = json.dumps(data, ensure_ascii=False)
                self._log(f"[调试] 完整响应: {resp_str[:500]}...")
            except Exception as e:
                self._log(f"[错误] API 请求失败: {e}")
                break

            if data.get('code') != 0:
                self._log(f"[错误] API 返回: code={data.get('code')}, msg={data.get('msg', '未知错误')}")
                self._log("[获取] 回退到页面解析方式...")
                return self._fetch_user_videos_from_page(user_url, output_file, cookies, headers, sec_user_id, user_id)

            notes = data.get('data', {}).get('notes', [])

            has_more = data.get('data', {}).get('has_more', False)
            next_cursor = data.get('data', {}).get('cursor', '')
            self._log(f"[调试] 分页信息: has_more={has_more}, next_cursor={next_cursor}, notes数量={len(notes)}")

            if not notes:
                self._log(f"[获取] 第 {page_num} 页无数据，结束获取")
                break

            for note in notes:
                note_type = note.get('type', '')
                if note_type == 'video':
                    note_id = note.get('noteId', '')
                    title = note.get('displayTitle', '') or note.get('title', '')
                    xsec_token = note.get('xsecToken', '')

                    if note_id:
                        if xsec_token:
                            url = f'https://www.xiaohongshu.com/user/profile/{user_id}/{note_id}?xsec_token={xsec_token}&xsec_source=pc_user'
                        else:
                            url = f'https://www.xiaohongshu.com/user/profile/{user_id}/{note_id}'

                        videos.append({
                            'note_id': note_id,
                            'title': title,
                            'url': url,
                            'xsec_token': xsec_token,
                            'desc': note.get('desc', '')
                        })

            self._log(f"[获取] 第 {page_num} 页: 获取 {len(notes)} 条笔记，其中 {sum(1 for n in notes if n.get('type') == 'video')} 个视频")

            if not has_more:
                self._log("[获取] 已获取所有视频")
                break

            cursor = next_cursor
            page_num += 1

            if page_num > 100:
                self._log("[警告] 达到最大页数限制")
                break

        self._log(f'[获取] 共找到 {len(videos)} 个视频')

        result = {
            "user_id": user_id,
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(videos),
            "videos": videos
        }

        if output_file:
            output_path = Path(output_file)
        else:
            output_path = VIDEO_LIST_FILE

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self._log(f"[获取] 已保存到: {output_path}")
        self._progress(100, "完成!")

        return result

    def _fetch_user_videos_from_page(self, user_url: str, output_file: str, cookies: dict, headers: dict, sec_user_id: str, user_id: str) -> dict:
        """从页面 HTML 解析视频列表（回退方法）"""
        self._log("[获取] 使用页面解析方式获取视频列表...")

        page_url = f"https://www.xiaohongshu.com/user/profile/{sec_user_id}"
        self._log(f"[调试] 请求页面: {page_url}")
        resp = requests.get(page_url, cookies=cookies, headers=headers, timeout=30)
        self._log(f"[调试] 响应状态: {resp.status_code}, 内容长度: {len(resp.text)}")

        start_marker = 'window.__INITIAL_STATE__='
        start_idx = resp.text.find(start_marker)

        self._log(f"[调试] 查找 __INITIAL_STATE__: {'找到' if start_idx != -1 else '未找到'}")

        if start_idx == -1:
            self._log(f"[调试] 页面内容前500字符: {resp.text[:500]}")
            raise ValueError("无法从页面提取数据，可能需要登录")

        json_start = start_idx + len(start_marker)
        json_text = resp.text[json_start:]
        json_text = json_text.replace(':undefined', ':null').replace(',undefined', ',null')

        decoder = json.JSONDecoder()
        try:
            state, _ = decoder.raw_decode(json_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"解析页面数据失败: {e}")

        videos = []

        def unwrap_vue(obj, depth=0):
            if depth > 5 or not obj:
                return obj
            if isinstance(obj, dict):
                if '_rawValue' in obj:
                    return unwrap_vue(obj['_rawValue'], depth + 1)
                if '_value' in obj:
                    return unwrap_vue(obj['_value'], depth + 1)
            return obj

        notes_data = None
        if 'user' in state and 'notes' in state['user']:
            notes_data = unwrap_vue(state['user']['notes'])

        def extract_notes(obj):
            notes = []
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and 'noteCard' in item:
                        notes.append(item)
                    elif isinstance(item, list):
                        notes.extend(extract_notes(item))
            return notes

        notes = extract_notes(notes_data) if notes_data else []

        for note in notes:
            card = note.get('noteCard', {})
            note_type = card.get('type', '')
            if note_type == 'video':
                note_id = card.get('noteId', '')
                title = card.get('displayTitle', '') or card.get('title', '')
                xsec_token = card.get('xsecToken', '')

                if note_id:
                    if xsec_token:
                        url = f'https://www.xiaohongshu.com/user/profile/{user_id}/{note_id}?xsec_token={xsec_token}&xsec_source=pc_user'
                    else:
                        url = f'https://www.xiaohongshu.com/user/profile/{user_id}/{note_id}'

                    videos.append({
                        'note_id': note_id,
                        'title': title,
                        'url': url,
                        'xsec_token': xsec_token,
                        'desc': card.get('desc', '')
                    })

        self._log(f'[获取] 找到 {len(videos)} 个视频')

        result = {
            "user_id": user_id,
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(videos),
            "videos": videos
        }

        if output_file:
            output_path = Path(output_file)
        else:
            output_path = VIDEO_LIST_FILE

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self._log(f"[获取] 已保存到: {output_path}")
        self._progress(100, "完成!")

        return result
