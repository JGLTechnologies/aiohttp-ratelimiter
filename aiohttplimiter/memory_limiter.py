from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp.web import Request, StreamResponse
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter

from aiohttplimiter.limiter import BaseRateLimitDecorator, KeyFunc, ErrorHandler, RouteHandler

__all__ = ("Limiter",)


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
    ) -> Callable[[RouteHandler], Callable[[Request], Coroutine[Any, Any, StreamResponse]]]:
        def wrapper(func: RouteHandler) -> Callable[[Request], Coroutine[Any, Any, StreamResponse]]:
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
