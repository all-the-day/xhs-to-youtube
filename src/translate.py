"""
翻译服务模块
使用 MyMemory API（免费，无需注册，每天 5000 字符限额）
"""

import json
import time
from typing import Dict, Any, Callable, Optional

import requests

from src.config import CONFIG_FILE


class TranslateError(Exception):
    """翻译失败异常"""
    pass


class TranslateService:
    """翻译服务类"""

    # MyMemory API 配置
    MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"
    MYMEMORY_DAILY_LIMIT = 5000  # 每日字符限额
    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF = 2.0

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        config: Dict[str, Any] = None
    ):
        self.log_callback = log_callback
        self._config = config

    def _log(self, message: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if self._config is not None:
            return self._config

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._log(f"[警告] 配置文件读取失败: {e}")
                self._config = {}
        else:
            self._config = {}
        return self._config

    def _handle_response_error(self, response: requests.Response, text: str) -> str:
        """
        处理响应错误
        
        Args:
            response: HTTP 响应
            text: 原文
            
        Returns:
            原文（失败时回退）
        """
        status_code = response.status_code
        
        if status_code == 429:
            self._log("[警告] MyMemory API 请求频率超限，请稍后重试")
        elif status_code == 403:
            self._log("[警告] MyMemory API 访问被拒绝，可能是配额用尽")
        elif status_code >= 500:
            self._log(f"[警告] MyMemory 服务器错误: HTTP {status_code}")
        else:
            self._log(f"[警告] MyMemory 翻译请求失败: HTTP {status_code}")
        
        return text

    def translate(
        self,
        text: str,
        target_type: str = "title",
        max_retries: int = None,
        timeout: int = None
    ) -> str:
        """
        翻译文本（使用 MyMemory API）
        
        Args:
            text: 要翻译的文本
            target_type: 翻译类型（title/description），目前未使用
            max_retries: 最大重试次数，默认 3
            timeout: 请求超时时间（秒），默认 15
            
        Returns:
            翻译后的文本，失败时返回原文
        """
        if not text or not text.strip():
            return text

        config = self._load_config()
        proxies = config.get('proxies')
        
        max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        timeout = timeout or self.DEFAULT_TIMEOUT

        last_error = None
        for attempt in range(max_retries):
            try:
                params = {
                    "q": text,
                    "langpair": "zh-CN|en"
                }

                response = requests.get(
                    self.MYMEMORY_API_URL,
                    params=params,
                    proxies=proxies,
                    timeout=timeout
                )

                if response.status_code != 200:
                    # 对于客户端错误（4xx），不重试
                    if 400 <= response.status_code < 500:
                        return self._handle_response_error(response, text)
                    # 对于服务器错误（5xx），重试
                    last_error = f"HTTP {response.status_code}"
                    if attempt < max_retries - 1:
                        wait_time = self.DEFAULT_BACKOFF ** attempt
                        self._log(f"[翻译] 服务器错误，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    return self._handle_response_error(response, text)

                result = response.json()

                if result.get("responseStatus") == 200 and result.get("responseData"):
                    translated = result["responseData"].get("translatedText", "")
                    if translated:
                        self._log(f"[翻译] {text[:20]}... -> {translated[:20]}...")
                        return translated

                # 检查是否是配额超限
                if result.get("responseStatus") == 429:
                    self._log("[警告] MyMemory 每日翻译配额已用尽，使用原文")
                    return text

                # 空结果，不重试
                self._log("[警告] MyMemory 翻译返回空结果，使用原文")
                return text

            except requests.Timeout:
                last_error = "请求超时"
                if attempt < max_retries - 1:
                    wait_time = self.DEFAULT_BACKOFF ** attempt
                    self._log(f"[翻译] 请求超时，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                    
            except requests.ConnectionError as e:
                last_error = f"网络连接失败: {e}"
                if attempt < max_retries - 1:
                    wait_time = self.DEFAULT_BACKOFF ** attempt
                    self._log(f"[翻译] 网络连接失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                    
            except json.JSONDecodeError:
                last_error = "响应解析失败"
                self._log(f"[警告] MyMemory 响应解析失败，使用原文")
                return text
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait_time = self.DEFAULT_BACKOFF ** attempt
                    self._log(f"[翻译] 翻译失败: {e}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

        # 所有重试都失败
        self._log(f"[警告] MyMemory 翻译失败（重试 {max_retries} 次后）: {last_error}，使用原文")
        return text