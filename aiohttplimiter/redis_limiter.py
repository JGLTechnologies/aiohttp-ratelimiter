from functools import wraps
import json
from typing import Callable, Awaitable, Union, Optional
import asyncio
from aiohttp.web import Request, Response
import limits.strategies
from .memory_limiter import default_keyfunc, RateLimitExceeded, Allow
from limits.storage import RedisStorage


class RateLimitDecorator:
    """
    Decorator to rate limit requests in the aiohttp.web framework with redis
    """

    def __init__(self, db: RedisStorage, path_id: str, keyfunc: Callable,
                 moving_window: limits.strategies.MovingWindowRateLimiter, ratelimit: str,
                 exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
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
        self.moving_window = moving_window
        if self.period >= 31_536_000:
            self.item = limits.RateLimitItemPerYear(self.calls, self.period / 31_536_000)
        elif self.period >= 2_628_000:
            self.item = limits.RateLimitItemPerMonth(self.calls, self.period / 2_628_000)
        elif self.period >= 86400:
            self.item = limits.RateLimitItemPerDay(self.calls, self.period / 86400)
        elif self.period >= 3600:
            self.item = limits.RateLimitItemPerHour(self.calls, self.period / 3600)
        elif self.period >= 60:
            self.item = limits.RateLimitItemPerMinute(self.calls, self.period / 60)
        else:
            self.item = limits.RateLimitItemPerSecond(self.calls, self.period)

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
                if not self.moving_window.test(self.item, db_key):
                    if self.error_handler is not None:
                        if asyncio.iscoroutinefunction(self.error_handler):
                            r = await self.error_handler(request, RateLimitExceeded(
                                **{"detail": f"{self._calls} request(s) per {self.period} second(s)"}))
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
                self.moving_window.hit(self.item, db_key)
                # Returns normal response if the user did not go over the rate limit
                return await func(request)
            else:
                # Checks if the user's IP is in the set of exempt IPs
                if default_keyfunc(request) in self.exempt_ips:
                    return func(request)

                # Returns a response if the number of calls exceeds the max amount of calls
                if not self.moving_window.test(self.item, db_key):
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
                self.moving_window.hit(self.item, db_key)
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

    def __init__(self, keyfunc: Callable, exempt_ips: Optional[set] = None,
                 error_handler: Optional[Union[Callable, Awaitable]] = None, **redis_args) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.db = RedisStorage(**redis_args)
        self.moving_window = limits.strategies.MovingWindowRateLimiter(self.db)
        self.error_handler = error_handler

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None,
              error_handler: Optional[Union[Callable, Awaitable]] = None, path_id: str = None) -> Callable:
        def wrapper(func: Callable) -> Awaitable:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return RateLimitDecorator(db=self.db, keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips,
                                      error_handler=_error_handler, path_id=path_id, moving_window=self.moving_window)(
                func)

        return wrapper
