"""
重试工具模块
提供通用的重试装饰器和异常类
"""

import functools
import time
from typing import Callable, Type, Tuple, Optional, Any


class RetryExhaustedError(Exception):
    """重试次数耗尽异常"""
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def with_retry(
    max_retries: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, int], None]] = None,
) -> Callable:
    """
    网络请求重试装饰器
    
    Args:
        max_retries: 最大重试次数
        backoff: 退避基数，实际等待时间为 backoff ** attempt
        exceptions: 需要重试的异常类型元组
        on_retry: 重试时的回调函数，参数为 (异常, 当前尝试次数, 最大尝试次数)
    
    Returns:
        装饰后的函数
    
    Example:
        @with_retry(max_retries=3, backoff=2.0, exceptions=(requests.Timeout,))
        def fetch_data():
            return requests.get("https://example.com", timeout=10)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = backoff ** attempt
                        if on_retry:
                            on_retry(e, attempt + 1, max_retries)
                        time.sleep(wait_time)
            raise RetryExhaustedError(
                f"重试 {max_retries} 次后仍然失败: {func.__name__}",
                last_error
            )
        return wrapper
    return decorator


def retry_call(
    func: Callable,
    args: tuple = (),
    kwargs: dict = None,
    max_retries: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, int], None]] = None,
) -> Any:
    """
    带重试的函数调用
    
    Args:
        func: 要调用的函数
        args: 位置参数
        kwargs: 关键字参数
        max_retries: 最大重试次数
        backoff: 退避基数
        exceptions: 需要重试的异常类型元组
        on_retry: 重试时的回调函数
    
    Returns:
        函数返回值
    
    Example:
        result = retry_call(
            requests.get,
            args=("https://example.com",),
            kwargs={"timeout": 10},
            max_retries=3,
            exceptions=(requests.Timeout,)
        )
    """
    if kwargs is None:
        kwargs = {}
    
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff ** attempt
                if on_retry:
                    on_retry(e, attempt + 1, max_retries)
                time.sleep(wait_time)
    
    raise RetryExhaustedError(
        f"重试 {max_retries} 次后仍然失败: {func.__name__}",
        last_error
    )