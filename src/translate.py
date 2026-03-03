"""
翻译服务模块
使用 MyMemory API（免费，无需注册，每天 5000 字符限额）
"""

import json
from typing import Dict, Any, Callable, Optional

from src.config import CONFIG_FILE


class TranslateService:
    """翻译服务类"""

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
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        else:
            self._config = {}
        return self._config

    def translate(self, text: str, target_type: str = "title") -> str:
        """
        翻译文本（使用 MyMemory API）
        
        Args:
            text: 要翻译的文本
            target_type: 翻译类型（title/description），目前未使用
            
        Returns:
            翻译后的文本，失败时返回原文
        """
        import requests

        config = self._load_config()
        proxies = config.get('proxies')

        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                "q": text,
                "langpair": "zh-CN|en"
            }

            response = requests.get(url, params=params, proxies=proxies, timeout=15)

            if response.status_code != 200:
                self._log(f"[警告] MyMemory 翻译请求失败: HTTP {response.status_code}")
                return text

            result = response.json()

            if result.get("responseStatus") == 200 and result.get("responseData"):
                translated = result["responseData"].get("translatedText", "")
                if translated:
                    self._log(f"[翻译] {text[:20]}... -> {translated[:20]}...")
                    return translated

            self._log("[警告] MyMemory 翻译返回空结果，使用原文")
            return text

        except Exception as e:
            self._log(f"[错误] MyMemory 翻译失败: {e}")
            return text