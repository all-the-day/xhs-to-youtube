"""
Pytest 共享配置。
"""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_network: requires network access and live xiaohongshu download",
    )


def pytest_collection_modifyitems(config, items):
    if os.getenv("XHS_RUN_LIVE_TESTS") == "1":
        return

    skip_live = pytest.mark.skip(
        reason="需要 XHS_RUN_LIVE_TESTS=1 和可用网络才能执行真实下载测试",
    )
    for item in items:
        if "live_network" in item.keywords:
            item.add_marker(skip_live)
