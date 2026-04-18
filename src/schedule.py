"""
定时调度模块

提供定时上传功能的执行逻辑。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.config import (
    SCHEDULE_LOG_FILE,
    ensure_logs_dir,
    get_schedule_task_for_time,
    load_schedule_config,
)


def _parse_schedule_time(time_str: str) -> datetime | None:
    """解析 HH:MM 格式的调度时间。"""
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return None


def setup_schedule_logger() -> logging.Logger:
    """设置调度日志记录器"""
    ensure_logs_dir()
    
    logger = logging.getLogger("schedule")
    logger.setLevel(logging.INFO)
    
    # 避免重复添加 handler
    if not logger.handlers:
        # 文件 handler
        file_handler = logging.FileHandler(
            SCHEDULE_LOG_FILE, encoding="utf-8", mode="a"
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 控制台 handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)
    
    return logger


def log_execution(
    logger: logging.Logger,
    task: dict[str, Any],
    result: dict[str, Any],
    error: str | None = None,
) -> None:
    """记录执行结果
    
    Args:
        logger: 日志记录器
        task: 任务配置
        result: 执行结果
        error: 错误信息（如果有）
    """
    time_str = task.get("time", "unknown")
    limit = task.get("limit", 0)
    success_count = result.get("success_count", 0)
    skipped = result.get("skipped", 0)
    failed = result.get("failed", 0)
    
    if error:
        # 有异常抛出
        logger.error(f"[{time_str}] 任务执行失败: {error}")
    elif failed == 0:
        # 完全成功
        logger.info(
            f"[{time_str}] 任务执行成功 - "
            f"计划: {limit}, 成功: {success_count}, 跳过: {skipped}, 失败: {failed}"
        )
    elif success_count > 0:
        # 部分成功
        logger.info(
            f"[{time_str}] 任务执行完成（部分成功）- "
            f"计划: {limit}, 成功: {success_count}, 跳过: {skipped}, 失败: {failed}"
        )
    else:
        # 完全失败（无成功上传）
        logger.warning(
            f"[{time_str}] 任务执行失败 - "
            f"计划: {limit}, 成功: {success_count}, 跳过: {skipped}, 失败: {failed}"
        )


def run_scheduled_upload(
    time_str: str | None = None,
    task_time: str | None = None,
    limit: int | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """执行定时上传任务
    
    Args:
        time_str: 时间字符串，格式为 "HH:MM"。如果为 None，则使用当前时间匹配
        task_time: `time_str` 的兼容别名，避免旧调用方出错
        limit: 上传数量限制。如果为 None，则从配置中获取
        log_callback: 日志回调函数
    
    Returns:
        执行结果字典
    """
    from src.core import XHSToYouTube
    
    # 设置日志
    logger = setup_schedule_logger()
    
    # 获取当前时间
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    # 确定任务时间
    task_time = time_str or task_time or current_time
    
    # 获取任务配置
    task = get_schedule_task_for_time(task_time)
    
    if not task:
        msg = f"未找到时间 {task_time} 对应的启用任务"
        logger.warning(msg)
        return {"success": False, "error": "task_not_found", "message": msg}
    
    # 确定上传数量
    upload_limit = limit if limit is not None else task.get("limit", 3)
    
    logger.info(f"开始执行定时上传任务 - 时间: {task_time}, 数量: {upload_limit}")
    
    if log_callback:
        log_callback(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 开始定时上传任务")
        log_callback(f"  时间: {task_time}, 计划上传: {upload_limit} 个视频")
    
    # 执行批量上传
    tool = XHSToYouTube()
    
    try:
        result = tool.batch_transfer(
            limit=upload_limit,
            translate=False,
            show_time_suggestion=False,  # 定时任务不需要时间确认
        )
        
        # 记录日志
        log_execution(logger, task, result)
        
        if log_callback:
            success_count = result.get("success_count", 0)
            skipped = result.get("skipped", 0)
            failed = result.get("failed", 0)
            log_callback(f"  结果: 成功 {success_count}, 跳过 {skipped}, 失败 {failed}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_execution(logger, task, {}, error=error_msg)
        
        if log_callback:
            log_callback(f"  错误: {error_msg}")
        
        return {"success": False, "error": "exception", "message": error_msg}


def list_schedule_tasks() -> list[dict[str, Any]]:
    """列出所有调度任务
    
    Returns:
        任务列表
    """
    config = load_schedule_config()
    return config.get("tasks", [])


def generate_crontab_entries(python_path: str | None = None) -> str:
    """生成 crontab 配置
    
    Args:
        python_path: Python 解释器路径。如果为 None，则使用系统 python3
    
    Returns:
        crontab 配置字符串
    """
    from src.config import SCRIPT_DIR
    
    tasks = list_schedule_tasks()
    python = python_path or "python3"
    work_dir = str(SCRIPT_DIR)
    
    lines = [
        "# 小红书视频定时上传任务",
        "# 由 xhs-to-youtube 自动生成",
        "",
    ]
    
    for task in tasks:
        if not task.get("enabled", True):
            continue
        
        time_str = task.get("time", "")
        limit = task.get("limit", 3)
        description = task.get("description", "")
        
        if not time_str:
            continue
        
        # 解析时间
        parts = time_str.split(":")
        if len(parts) != 2:
            continue
        
        hour, minute = parts[0], parts[1]
        
        # 生成 crontab 条目
        entry = (
            f"# {description}\n"
            f"{minute} {hour} * * * cd {work_dir} && {python} -m src.cli schedule --time {time_str} --limit {limit} >> logs/cron.log 2>&1"
        )
        lines.append(entry)
        lines.append("")
    
    return "\n".join(lines)


def get_today_schedule_status() -> dict[str, Any]:
    """获取今日调度状态
    
    Returns:
        包含今日任务执行状态的字典
    """
    from src.config import UPLOADED_FILE
    
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    
    # 加载任务配置
    tasks = list_schedule_tasks()
    
    # 加载今日上传记录
    today_uploads = 0
    if UPLOADED_FILE.exists():
        try:
            with open(UPLOADED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data.get("records", {})
                for record in records.values():
                    uploaded_at = record.get("uploaded_at", "")
                    if uploaded_at.startswith(today_str):
                        today_uploads += 1
        except (json.JSONDecodeError, IOError):
            pass
    
    # 分析任务状态
    task_status = []
    for task in tasks:
        if not task.get("enabled", True):
            continue
        
        time_str = task.get("time", "")
        limit = task.get("limit", 3)
        
        # 解析时间
        if not _parse_schedule_time(time_str):
            continue

        # 判断任务状态，精确到分钟
        if current_time > time_str:
            status = "completed"
        elif current_time == time_str:
            status = "running"
        else:
            status = "pending"
        
        task_status.append({
            "time": time_str,
            "limit": limit,
            "description": task.get("description", ""),
            "status": status,
        })
    
    return {
        "date": today_str,
        "current_time": now.strftime("%H:%M"),
        "today_uploads": today_uploads,
        "tasks": task_status,
    }
