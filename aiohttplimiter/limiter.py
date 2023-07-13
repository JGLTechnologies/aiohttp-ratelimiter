from functools import wraps
import json
from typing import Callable, Awaitable, Union, Optional, Coroutine, Any
import asyncio
from aiohttp.web import Request, Response, View
from limits.aio.storage import Storage, MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from limits import parse


def default_keyfunc(ctx: Union[Request, View]) -> str:
    """
    Returns the user's IP
    """
    if isinstance(ctx, View):
        request = ctx.request
    else:
        request = ctx
    ip = request.headers.get(
        "X-Forwarded-For") or request.remote or "127.0.0.1"
    ip = ip.split(",")[0]
    return ip


class Allow:
    def __init__(self) -> None:
        pass


class RateLimitExceeded:
    def __init__(self, detail: str) -> None:
        self._detail = detail

    @property
    def detail(self):
        return self._detail


class BaseRateLimitDecorator:
    def __init__(self, db: Storage, path_id: str, keyfunc: Callable,
                 moving_window: MovingWindowRateLimiter, ratelimit: str,
                 exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
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

    def __call__(self, func: Union[Callable, Awaitable]) -> Callable[[Union[Request, View]], Coroutine[Any, Any, Response]]:
        @wraps(func)
        async def wrapper(ctx: Union[Request, View]) -> Response:
            if isinstance(ctx, View):
                request = ctx.request
            else:
                request = ctx
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
                    if asyncio.iscoroutinefunction(self.error_handler):
                        r = await self.error_handler(request, RateLimitExceeded(self.amount))
                        if isinstance(r, Allow):
                            return await func(request)
                        return r
                    else:
                        r = self.error_handler(request, RateLimitExceeded(self.amount))
                        if isinstance(r, Allow):
                            return await func(request)
                        return r
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
            if asyncio.iscoroutinefunction(func):
                return await func(ctx)
            else:
                return func(ctx)

        return wrapper
