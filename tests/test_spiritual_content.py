#!/usr/bin/env python3
"""readBiblecontext 联调相关测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# 添加项目路径，支持直接运行该文件
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core import XHSToYouTube
from src.spiritual_content import SpiritualContentClient
from src.translate import TranslateService


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_spiritual_client_disabled_by_default():
    client = SpiritualContentClient(config={"spiritual_content": {"enabled": False}})

    assert client.enabled() is False
    assert client.compose("测试文本") is None


def test_spiritual_client_parses_compose_response():
    captured: dict[str, Any] = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "ok": True,
                "kind": "compose",
                "data": {
                    "short_title": "安息与轻省",
                    "lines": [
                        "主的同在带来安息。",
                        "心里有主，就不至于慌乱。",
                    ],
                    "references": ["马太福音 11:28", "腓立比书 4:7"],
                    "confidence": 0.91,
                    "theme": "安息",
                    "source_hits": [{"kind": "verse", "ref": "太 11:28"}],
                },
            }
        )

    import src.spiritual_content as spiritual_content_module

    original_post = spiritual_content_module.requests.post
    spiritual_content_module.requests.post = fake_post

    try:
        client = SpiritualContentClient(
            config={
                "spiritual_content": {
                    "enabled": True,
                    "api_url": "http://127.0.0.1:8080",
                    "api_key": "secret",
                    "timeout": 9,
                    "style": "gentle",
                }
            }
        )

        result = client.compose("测试描述", tags=["日常"], context="https://example.com", length=4, target_lang="en")

        assert result is not None
        assert result.short_title == "安息与轻省"
        assert result.lines == ["主的同在带来安息。", "心里有主，就不至于慌乱。"]
        assert result.references == ["马太福音 11:28", "腓立比书 4:7"]
        assert abs(result.confidence - 0.91) < 1e-9
        assert result.theme == "安息"
        assert result.source_hits == [{"kind": "verse", "ref": "太 11:28"}]
        assert captured["url"] == "http://127.0.0.1:8080/compose"
        assert captured["json"]["text"] == "测试描述"
        assert captured["json"]["tags"] == ["日常"]
        assert captured["json"]["context"] == "https://example.com"
        assert captured["json"]["length"] == 4
        assert captured["json"]["include_references"] is True
        assert captured["json"]["style"] == "gentle"
        assert captured["json"]["target_lang"] == "en"
        assert captured["headers"]["X-API-Key"] == "secret"
        assert captured["timeout"] == 9
    finally:
        spiritual_content_module.requests.post = original_post


def test_generate_description_includes_spiritual_lines():
    tool = XHSToYouTube()

    class _FakeSpiritualClient:
        def compose(self, *args, **kwargs):
            from src.spiritual_content import SpiritualContentResult

            return SpiritualContentResult(
                short_title="安息与轻省",
                lines=["主的同在带来安息。", "心里有主，就不至于慌乱。"],
                references=["马太福音 11:28", "腓立比书 4:7"],
                confidence=0.9,
                theme="安息",
                source_hits=[],
            )

    tool.spiritual_content = _FakeSpiritualClient()
    desc = tool.generate_description("测试描述", "https://example.com", "uploader")

    assert "属灵短句" in desc
    assert "安息与轻省" in desc
    assert "- 主的同在带来安息。" in desc
    assert "参考：马太福音 11:28；腓立比书 4:7" in desc


def test_generate_description_falls_back_to_default_when_disabled():
    tool = XHSToYouTube()
    tool.spiritual_content = SpiritualContentClient(config={"spiritual_content": {"enabled": False}})

    desc = tool.generate_description("测试描述", "https://example.com", "uploader")

    assert "测试描述" in desc
    assert "原创" in desc
    assert "属灵短句" not in desc


def test_translate_service_uses_translation_api_first():
    captured: dict[str, Any] = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        class _Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "ok": True,
                    "kind": "translate",
                    "data": {
                        "translated_text": "Spiritual Lines\n- Joy in the Lord\nOriginal Content",
                        "method": "api",
                        "confidence": 0.95,
                    },
                }

        return _Resp()

    import src.translate as translate_module

    original_post = translate_module.requests.post
    translate_module.requests.post = fake_post
    try:
        service = TranslateService(config={
            "translation_api": {
                "enabled": True,
                "api_url": "http://127.0.0.1:8080",
                "api_key": "secret",
                "timeout": 9,
                "source_lang": "zh-CN",
                "target_lang": "en",
                "mode": "spiritual",
                "preserve_lines": True,
            }
        })
        result = service.translate("属灵短句\n主里喜乐\n原创", target_type="description")
        assert "Spiritual Lines" in result
        assert captured["url"] == "http://127.0.0.1:8080/translate"
        assert captured["json"]["mode"] == "spiritual"
        assert captured["json"]["preserve_lines"] is True
    finally:
        translate_module.requests.post = original_post


def test_generate_description_translates_spiritual_block_when_enabled():
    tool = XHSToYouTube()

    class _FakeSpiritualClient:
        def compose(self, *args, **kwargs):
            from src.spiritual_content import SpiritualContentResult

            target_lang = kwargs.get("target_lang", "zh")
            return SpiritualContentResult(
                short_title="Joy in the Lord" if target_lang == "en" else "主里喜乐",
                lines=[
                    "Rejoice in the Lord always",
                    "When the Lord is in the heart, ordinary days can shine",
                ] if target_lang == "en" else ["你们要在主里常常喜乐", "当心里有主，日常也会有光"],
                references=["Philippians 4:4"] if target_lang == "en" else ["腓立比书 4:4"],
                confidence=0.9,
                theme="joy",
                source_hits=[],
            )

    tool.spiritual_content = _FakeSpiritualClient()

    desc = tool.generate_description("今天很喜悦", "https://example.com", "uploader", translate=True)

    assert desc.startswith("Spiritual Lines")
    assert "Joy in the Lord" in desc
    assert "Rejoice in the Lord always" in desc
    assert "Philippians 4:4" in desc


if __name__ == "__main__":
    test_spiritual_client_disabled_by_default()
    test_spiritual_client_parses_compose_response()
    test_generate_description_includes_spiritual_lines()
    test_generate_description_falls_back_to_default_when_disabled()
    test_translate_service_uses_translation_api_first()
    test_generate_description_translates_spiritual_block_when_enabled()
    print("spiritual_content_smoke_ok")
