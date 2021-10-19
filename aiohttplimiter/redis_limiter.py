from functools import wraps
import time
import json
from typing import Callable, Awaitable, Union
import asyncio
from typing import Optional
from aiohttp.web import Request, Response
import aioredis
from .decorators import default_keyfunc, RateLimitExceeded, Allow


IntOrFloat = Union[int, float]
def now(): return time.time()


class RateLimitDecorator:
    """
    Decorator to rate limit requests in the aiohttp.web framework with redis
    """

    def __init__(self, db: aioredis.Redis, keyfunc: Callable, ratelimit: str, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
        self.exempt_ips = exempt_ips or set()
        calls, period = ratelimit.split("/")
        self._calls = calls
        calls = int(calls)
        period = int(period)
        assert period > 0
        assert calls > 0
        self.period = period
        self.keyfunc = keyfunc
        self.calls = calls
        self.db = db
        self.error_handler = error_handler

    def __call__(self, func: Callable) -> Awaitable:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            self.func = func
            key = self.keyfunc(request)
            db_key = f"{key}:{str(id(func))}"

            # Checks if the user's IP is in the set of exempt IPs
            if default_keyfunc(request) in self.exempt_ips:
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)

            # Returns a response if the number of calls exceeds the max amount of calls
            nc = await self.db.get(db_key)
            nc = int(nc.decode()) if nc is not None else 1
            print(nc)
            if nc >= self.calls:
                if self.error_handler is not None:
                    if asyncio.iscoroutinefunction(self.error_handler):
                        r = await self.error_handler(request, RateLimitExceeded(**{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                        if isinstance(r, Allow):
                            if asyncio.iscoroutinefunction(func):
                                return await func(request)
                            return func(request)
                        return r
                    else:
                        r = self.error_handler(request, RateLimitExceeded(
                            **{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                        if isinstance(r, Allow):
                            if asyncio.iscoroutinefunction(func):
                                return await func(request)
                            return func(request)
                        return r
                data = json.dumps(
                    {"error": f"Rate limit exceeded: {self._calls} request(s) per {self.period} second(s)"})
                response = Response(
                    text=data, content_type="application/json", status=429)
                response.headers.add(
                    "error", f"Rate limit exceeded: {self._calls} request(s) per {self.period} second(s)")
                return response

            # Increments the number of calls by 1
            await self.db.incr(db_key)
            await self.db.expire(db_key, self.period)
            # Returns normal response if the user did not go over the rate limit
            if asyncio.iscoroutinefunction(func):
                return await func(request)
            return func(request)

        return wrapper


class RedisLimiter:
    """
    ```
    limiter = Limiter(keyfunc=your_keyfunc)
    @routes.get("/")
    @limiter.limit("5/1")
    def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(self, keyfunc: Callable, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None, **redis_args) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.db = aioredis.Redis(**redis_args)
        self.error_handler = error_handler

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None, middleware_count: int = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> Callable:
        def wrapper(func: Callable) -> Awaitable:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return RateLimitDecorator(db=self.db, keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips, error_handler=_error_handler)(func)
        return wrapper
