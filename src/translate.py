"""
翻译服务模块
支持多种翻译 API：DeepLX、有道、DeepL、OpenAI
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

    def _translate_with_youdao(self, text: str) -> str:
        """
        使用有道翻译 API（免费，无需注册）
        """
        import requests

        config = self._load_config()
        proxies = config.get('proxies')

        try:
            url = "https://fanyi.youdao.com/translate"
            params = {
                "doctype": "json",
                "type": "ZH_CN2EN",
                "i": text
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://fanyi.youdao.com/"
            }

            response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=15)

            if response.status_code != 200:
                self._log(f"[警告] 有道翻译请求失败: HTTP {response.status_code}")
                return text

            result = response.json()

            if result.get("translateResult"):
                translations = result["translateResult"][0]
                if translations:
                    translated = " ".join([t.get("tgt", "") for t in translations if t.get("tgt")])
                    if translated:
                        self._log(f"[翻译] {text[:20]}... -> {translated[:20]}...")
                        return translated

            self._log("[警告] 有道翻译返回空结果，使用原文")
            return text

        except Exception as e:
            self._log(f"[错误] 有道翻译失败: {e}")
            return text

    def _translate_with_deeplx(self, text: str) -> str:
        """
        使用 DeepLX API 翻译文本（免费，需本地部署）
        """
        import requests

        config = self._load_config()
        deeplx_url = config.get('deeplx_url', 'http://localhost:1188')
        proxies = config.get('proxies')

        url = f"{deeplx_url.rstrip('/')}/v1/translate"

        try:
            response = requests.post(
                url,
                json={
                    "text": text,
                    "source_lang": "ZH",
                    "target_lang": "EN"
                },
                headers={"Content-Type": "application/json"},
                proxies=proxies,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 200 and result.get("data"):
                translated = result["data"]
                self._log(f"[翻译] {text[:20]}... -> {translated[:20]}...")
                return translated

            self._log("[警告] DeepLX 返回空结果")
            return text

        except Exception as e:
            self._log(f"[错误] DeepLX 翻译失败: {e}")
            return text

    def _translate_with_deepl(self, text: str) -> str:
        """
        使用 DeepL API 翻译文本
        """
        import requests

        config = self._load_config()
        api_key = config.get('deepl_api_key')

        if not api_key:
            self._log("[警告] 未配置 DeepL API Key，跳过翻译")
            return text

        use_free = config.get('deepl_free', True)
        if use_free:
            url = "https://api-free.deepl.com/v2/translate"
        else:
            url = "https://api.deepl.com/v2/translate"

        try:
            response = requests.post(
                url,
                data={
                    "auth_key": api_key,
                    "text": text,
                    "source_lang": "ZH",
                    "target_lang": "EN"
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["translations"][0]["text"]
        except Exception as e:
            self._log(f"[错误] DeepL 翻译失败: {e}")
            return text

    def _translate_with_openai(self, text: str, target_type: str = "title") -> str:
        """
        使用 OpenAI API 翻译文本
        """
        config = self._load_config()
        api_key = config.get('openai_api_key')

        if not api_key:
            self._log("[警告] 未配置 OpenAI API Key，跳过翻译")
            return text

        try:
            from openai import OpenAI
        except ImportError:
            self._log("[错误] 请安装 openai 库: pip install openai")
            return text

        base_url = config.get('openai_base_url', 'https://api.openai.com/v1')
        model = config.get('openai_model', 'gpt-4o-mini')

        if target_type == "title":
            system_prompt = """You are a YouTube title translator. Translate Chinese video titles to English.
Rules:
- Style: casual, catchy, YouTube-friendly
- Keep it concise (under 60 characters if possible)
- Make it engaging for English-speaking audience
- Only output the English translation, no explanations"""
        else:
            system_prompt = """You are a YouTube description translator. Translate Chinese video descriptions to English.
Rules:
- Style: casual, conversational, engaging
- Make it natural for English-speaking audience
- Keep the original meaning and emotion
- Only output the English translation, no explanations"""

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=500 if target_type == "description" else 100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self._log(f"[错误] 翻译失败: {e}")
            return text

    def translate(self, text: str, target_type: str = "title") -> str:
        """
        翻译文本（自动选择翻译服务）

        优先级：DeepLX > 有道翻译 > DeepL > OpenAI
        """
        config = self._load_config()

        # 优先使用 DeepLX
        if config.get('deeplx_url') or not config.get('disable_deeplx'):
            result = self._translate_with_deeplx(text)
            if result != text:
                return result

        # 有道翻译
        if not config.get('disable_youdao'):
            result = self._translate_with_youdao(text)
            if result != text:
                return result

        # DeepL
        if config.get('deepl_api_key'):
            return self._translate_with_deepl(text)

        # OpenAI
        if config.get('openai_api_key'):
            return self._translate_with_openai(text, target_type)

        return text
