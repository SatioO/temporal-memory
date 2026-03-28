from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def bind_handler(fn: Callable[..., Awaitable[T]], **deps):
    async def wrapper(req):
        return await fn(req, **deps)

    return wrapper
