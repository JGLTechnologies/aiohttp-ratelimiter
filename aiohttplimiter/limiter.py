from __future__ import annotations

import functools
import json

from collections.abc import Callable, Awaitable, Coroutine
from typing import Any, Union, Type

from aiohttp.abc import AbstractView
from aiohttp.web import Request, Response, StreamResponse

from limits.aio.storage import Storage, MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from limits import parse

__all__ = (
    "Allow",
    "RateLimitExceeded",
    "default_keyfunc"
)

RouteHandler = Union[Type[AbstractView], Callable[[Request], Awaitable[StreamResponse]]]
ErrorHandler = Callable[[Request, "RateLimitExceeded"], Awaitable["Allow | StreamResponse"]]
KeyFunc = Callable[[Request], str]


def default_keyfunc(request: Request) -> str:
    """
    Returns the user's IP
    """
    ip = request.headers.get("X-Forwarded-For") or request.remote or "127.0.0.1"
    ip = ip.split(",")[0]
    return ip


class Allow:
    def __init__(self) -> None:
        pass


class RateLimitExceeded:
    def __init__(self, detail: str) -> None:
        self._detail = detail

    @property
    def detail(self) -> str:
        return self._detail


class BaseRateLimitDecorator:
    def __init__(
        self,
        db: Storage,
        path_id: str | None,
        keyfunc: KeyFunc,
        moving_window: MovingWindowRateLimiter,
        ratelimit: str,
        exempt_ips: set[str] | None = None,
        error_handler: ErrorHandler | None = None
    ) -> None:
        self.exempt_ips = exempt_ips or set()
        self.item = parse(ratelimit)
        calls = self.item.amount
        if int(self.item.multiples) > 1:
            self.amount = f"{calls} request(s) per {self.item.multiples} {self.item.GRANULARITY.name}s"
        else:
            self.amount = f"{calls} request(s) per {self.item.GRANULARITY.name}"
        self.period = self.item.amount
        self.keyfunc = keyfunc
        self.calls = calls
        self.db = db
        self.error_handler = error_handler
        self.path_id = path_id
        self.moving_window = moving_window

    def __call__(self, func: RouteHandler) -> Callable[[Request], Coroutine[Any, Any, StreamResponse]]:
        @functools.wraps(func)
        async def wrapper(request: Request) -> StreamResponse:
            key = self.keyfunc(request)
            db_key = f"{key}:{self.path_id or request.path}"

            if isinstance(self.db, MemoryStorage):
                if not await self.db.check():
                    await self.db.reset()

            # Checks if the user's IP is in the set of exempt IPs
            if default_keyfunc(request) in self.exempt_ips:
                return await func(request)

            # Returns a response if the number of calls exceeds the max amount of calls
            if not await self.moving_window.test(self.item, db_key):
                if self.error_handler is not None:
                    response = await self.error_handler(request, RateLimitExceeded(self.amount))
                    if isinstance(response, Allow):
                        return await func(request)
                    return response
                data = json.dumps(
                    {"error": f"Rate limit exceeded: {self.amount}"})
                response = Response(
                    text=data, content_type="application/json", status=429)
                response.headers.add(
                    "error", f"Rate limit exceeded: {self.amount}")
                return response

            # Increments the number of calls by 1
            await self.moving_window.hit(self.item, db_key)
            # Returns normal response if the user did not go over the rate limit
            return await func(request)

        return wrapper
