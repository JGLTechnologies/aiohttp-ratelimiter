from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, Union

from limits.aio.storage import MemcachedStorage
from limits.aio.strategies import MovingWindowRateLimiter

from aiohttplimiter.limiter import AsyncHandler, BaseRateLimitDecorator, ErrorHandler, KeyFunc, RouteHandler

__all__ = ("MemcachedLimiter",)

ViewOrRequestT = TypeVar("ViewOrRequestT", bound="AbstractView | Request")


class MemcachedLimiter:
    """
    ```
    routes = RouteTableDef()
    limiter = MemcachedLimiter(keyfunc=your_keyfunc, uri="memcached://localhost:11211")
    @routes.get("/")
    @limiter.limit("5/second")
    async def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(
        self,
        keyfunc: KeyFunc,
        uri: str,
        exempt_ips: Union[set[str], None] = None,
        error_handler: ErrorHandler | None = None,
        **options: Union[float, str, bool]
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
        exempt_ips: Union[set[str], None] = None,
        error_handler: ErrorHandler | None = None,
        path_id: Union[str, None] = None
    ) -> Callable[[RouteHandler[ViewOrRequestT]], AsyncHandler[ViewOrRequestT]]:
        def wrapper(func: RouteHandler[ViewOrRequestT]) -> AsyncHandler[ViewOrRequestT]:
            return BaseRateLimitDecorator(
                db=self.db,
                keyfunc=keyfunc or self.keyfunc,
                ratelimit=ratelimit,
                exempt_ips=exempt_ips or self.exempt_ips,
                error_handler=self.error_handler or error_handler,
                path_id=path_id,
                moving_window=self.moving_window
            )(func)

        return wrapper
