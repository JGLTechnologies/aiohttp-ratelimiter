from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from aiohttp.abc import AbstractView
from aiohttp.web import Request
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter

from aiohttplimiter.limiter import AsyncHandler, BaseRateLimitDecorator, KeyFunc, ErrorHandler, RouteHandler

__all__ = ("Limiter",)

ViewOrRequestT = TypeVar("ViewOrRequestT", bound="AbstractView | Request")


class Limiter:
    """
    ```
    routes = RouteTableDef()
    limiter = Limiter(keyfunc=your_keyfunc)

    @routes.get("/")
    @limiter.limit("5/second")
    async def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(
        self,
        keyfunc: KeyFunc,
        exempt_ips: set[str] | None = None,
        error_handler: ErrorHandler | None = None
    ) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.error_handler = error_handler
        self.db = MemoryStorage()
        self.moving_window = MovingWindowRateLimiter(self.db)

    def limit(
        self,
        ratelimit: str,
        keyfunc: KeyFunc | None = None,
        exempt_ips: set[str] | None = None,
        error_handler: ErrorHandler | None = None,
        path_id: str | None = None
    ) -> Callable[[RouteHandler[ViewOrRequestT]], AsyncHandler[ViewOrRequestT]]:
        def wrapper(func: RouteHandler[ViewOrRequestT]) -> AsyncHandler[ViewOrRequestT]:
            return BaseRateLimitDecorator(
                keyfunc=keyfunc or self.keyfunc,
                ratelimit=ratelimit,
                exempt_ips=exempt_ips or self.exempt_ips,
                error_handler=self.error_handler or error_handler,
                db=self.db, path_id=path_id,
                moving_window=self.moving_window
            )(func)

        return wrapper

    async def reset(self) -> None:
        await self.db.reset()
