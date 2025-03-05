from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp.web import Request, StreamResponse
from limits.aio.storage import MemcachedStorage
from limits.aio.strategies import MovingWindowRateLimiter

from aiohttplimiter.limiter import BaseRateLimitDecorator, ErrorHandler, KeyFunc, RouteHandler

__all__ = ("MemcachedLimiter",)


class MemcachedLimiter:
    """
    ```
    routes = RouteTableDef()
    limiter = MemcachedLimiter(keyfunc=your_keyfunc, uri="memcached://localhost:11211")
    @routes.get("/")
    @limiter.limit("5/1")
    async def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(
        self,
        keyfunc: KeyFunc,
        uri: str,
        exempt_ips: set[str] | None = None,
        error_handler: ErrorHandler | None = None,
        **options: float | str | bool
    ) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.db = MemcachedStorage(uri, **options)
        self.moving_window = MovingWindowRateLimiter(self.db)
        self.error_handler = error_handler

    def limit(
        self,
        ratelimit: str,
        keyfunc: KeyFunc | None = None,
        exempt_ips: set[str] | None = None,
        error_handler: ErrorHandler | None = None,
        path_id: str | None = None
    ) -> Callable[[RouteHandler], Callable[[Request], Coroutine[Any, Any, StreamResponse]]]:
        def wrapper(func: RouteHandler) -> Callable[[Request], Coroutine[Any, Any, StreamResponse]]:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return BaseRateLimitDecorator(
                db=self.db,
                keyfunc=_keyfunc,
                ratelimit=ratelimit,
                exempt_ips=_exempt_ips,
                error_handler=_error_handler,
                path_id=path_id,
                moving_window=self.moving_window
            )(func)

        return wrapper
