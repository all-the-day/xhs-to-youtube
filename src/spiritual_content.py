"""
readBiblecontext 联调客户端

用于从外部轻量服务获取属灵短句和短标题。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.config import load_config


@dataclass
class SpiritualContentResult:
    short_title: str
    lines: list[str]
    references: list[str]
    confidence: float = 0.0
    theme: str = ""
    source_hits: list[dict[str, Any]] | None = None


class SpiritualContentClient:
    """从 readBiblecontext 获取属灵内容。"""

    def __init__(self, log_callback=None, config: dict[str, Any] | None = None):
        self.log_callback = log_callback
        self._config = config

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _load_config(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config
        self._config = load_config()
        return self._config

    def _get_settings(self) -> dict[str, Any]:
        config = self._load_config()
        return config.get("spiritual_content", {})

    def enabled(self) -> bool:
        settings = self._get_settings()
        return bool(settings.get("enabled", False) and settings.get("api_url"))

    def compose(
        self,
        text: str,
        tags: list[str] | None = None,
        context: str | None = None,
        length: int = 4,
        target_lang: str = "zh",
    ) -> SpiritualContentResult | None:
        settings = self._get_settings()
        if not settings.get("enabled", False):
            return None

        api_url = settings.get("api_url", "").rstrip("/")
        if not api_url:
            return None

        payload = {
            "text": text,
            "tags": tags or [],
            "context": context or "",
            "length": length,
            "include_references": True,
            "style": settings.get("style", "normal"),
            "target_lang": target_lang,
        }

        headers = {"Content-Type": "application/json"}
        api_key = settings.get("api_key", "")
        if api_key:
            headers["X-API-Key"] = api_key

        timeout = settings.get("timeout", 15)
        try:
            response = requests.post(
                f"{api_url}/compose",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                self._log(f"[灵粮] API 返回失败: {data}")
                return None

            content = data.get("data", {}) or {}
            return SpiritualContentResult(
                short_title=content.get("short_title", ""),
                lines=content.get("lines", []) or [],
                references=content.get("references", []) or [],
                confidence=float(content.get("confidence", 0.0) or 0.0),
                theme=content.get("theme", ""),
                source_hits=content.get("source_hits", []) or [],
            )
        except Exception as e:
            self._log(f"[灵粮] 调用 readBiblecontext 失败: {e}")
            return None
