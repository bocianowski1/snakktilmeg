from functools import wraps
from time import perf_counter

from lib.logging import get_logger


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            get_logger(func.__module__).info(
                "function timed",
                extra={
                    "event": "function_timed",
                    "function": func.__name__,
                    "duration_seconds": perf_counter() - start,
                },
            )

    return wrapper
