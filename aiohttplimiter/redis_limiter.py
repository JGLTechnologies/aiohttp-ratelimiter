from functools import wraps
import json
from typing import Callable, Awaitable, Union, Optional
import asyncio
from aiohttp.web import Request, Response
import aioredis
from .memory_limiter import default_keyfunc, RateLimitExceeded, Allow


class RateLimitDecorator:
    """
    Decorator to rate limit requests in the aiohttp.web framework with redis
    """

    def __init__(self, db: aioredis.Redis, path_id: str, keyfunc: Callable, ratelimit: str, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
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
        self.path_id = path_id

    def __call__(self, func: Callable) -> Awaitable:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            db = self.db
            key = self.keyfunc(request)
            db_key = f"{key}:{self.path_id or request.path}"

            if asyncio.iscoroutinefunction(func):
                # Checks if the user's IP is in the set of exempt IPs
                if default_keyfunc(request) in self.exempt_ips:
                    return await func(request)

                # Returns a response if the number of calls exceeds the max amount of calls
                nc = await db.get(db_key)
                nc = int(nc.decode()) if nc is not None else 0
                if nc >= self.calls:
                    if self.error_handler is not None:
                        if asyncio.iscoroutinefunction(self.error_handler):
                            r = await self.error_handler(request, RateLimitExceeded(**{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                            if isinstance(r, Allow):
                                return await func(request)
                            return r
                        else:
                            r = self.error_handler(request, RateLimitExceeded(
                                **{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                            if isinstance(r, Allow):
                                return await func(request)
                            return r
                    data = json.dumps(
                        {"error": f"Rate limit exceeded: {self._calls} request(s) per {self.period} second(s)"})
                    response = Response(
                        text=data, content_type="application/json", status=429)
                    response.headers.add(
                        "error", f"Rate limit exceeded: {self._calls} request(s) per {self.period} second(s)")
                    return response

                # Increments the number of calls by 1
                await db.incr(db_key)
                await db.expire(db_key, self.period)
                # Returns normal response if the user did not go over the rate limit
                return await func(request)
            else:
                # Checks if the user's IP is in the set of exempt IPs
                if default_keyfunc(request) in self.exempt_ips:
                    return func(request)

                # Returns a response if the number of calls exceeds the max amount of calls
                nc = await db.get(db_key)
                nc = int(nc.decode()) if nc is not None else 0
                if nc >= self.calls:
                    if self.error_handler is not None:
                        if asyncio.iscoroutinefunction(self.error_handler):
                            r = await self.error_handler(request, RateLimitExceeded(
                                **{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                            if isinstance(r, Allow):
                                return func(request)
                            return r
                        else:
                            r = self.error_handler(request, RateLimitExceeded(
                                **{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
                            if isinstance(r, Allow):
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
                await db.incr(db_key)
                await db.expire(db_key, self.period)
                # Returns normal response if the user did not go over the rate limit
                return func(request)
        return wrapper


class RedisLimiter:
    """
    ```
    limiter = RedisLimiter(keyfunc=your_keyfunc, host="localhost", port=7634, password="12345")
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

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None, middleware_count: int = None, error_handler: Optional[Union[Callable, Awaitable]] = None, path_id: str = None) -> Callable:
        def wrapper(func: Callable) -> Awaitable:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return RateLimitDecorator(db=self.db, keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips, error_handler=_error_handler, path_id=path_id)(func)
        return wrapper
