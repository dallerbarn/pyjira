from asyncio import get_event_loop
from collections.abc import Callable
from typing import Any, Awaitable


def background_task(func: Callable[[Any, Any], Awaitable[None]]):
    def inner(*args: Any, **kwargs):
        get_event_loop().create_task(func(*args, **kwargs))
    return inner
