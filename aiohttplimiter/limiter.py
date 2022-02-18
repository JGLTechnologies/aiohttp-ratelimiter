from functools import wraps
import json
from typing import Callable, Awaitable, Union, Optional
import asyncio
from aiohttp.web import Request, Response
from limits.aio.storage import Storage, MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from limits import RateLimitItemPerYear, RateLimitItemPerMonth, RateLimitItemPerDay, RateLimitItemPerHour, \
    RateLimitItemPerMinute, RateLimitItemPerSecond


def default_keyfunc(request: Request) -> str:
    """
    Returns the user's IP
    """
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
            self.item = RateLimitItemPerYear(self.calls, self.period / 31_536_000)
        elif self.period >= 2_628_000:
            self.item = RateLimitItemPerMonth(self.calls, self.period / 2_628_000)
        elif self.period >= 86400:
            self.item = RateLimitItemPerDay(self.calls, self.period / 86400)
        elif self.period >= 3600:
            self.item = RateLimitItemPerHour(self.calls, self.period / 3600)
        elif self.period >= 60:
            self.item = RateLimitItemPerMinute(self.calls, self.period / 60)
        else:
            self.item = RateLimitItemPerSecond(self.calls, self.period)

    def __call__(self, func: Union[Callable, Awaitable]) -> Awaitable:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            key = self.keyfunc(request)
            db_key = f"{key}:{self.path_id or request.path}"

            if isinstance(self.db, MemoryStorage):
                if not await self.db.check():
                    await self.db.reset()

            if asyncio.iscoroutinefunction(func):
                # Checks if the user's IP is in the set of exempt IPs
                if default_keyfunc(request) in self.exempt_ips:
                    return await func(request)

                # Returns a response if the number of calls exceeds the max amount of calls
                if not await self.moving_window.test(self.item, db_key):
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
                await self.moving_window.hit(self.item, db_key)
                # Returns normal response if the user did not go over the rate limit
                return await func(request)
            else:
                # Checks if the user's IP is in the set of exempt IPs
                if default_keyfunc(request) in self.exempt_ips:
                    return func(request)

                # Returns a response if the number of calls exceeds the max amount of calls
                if not await self.moving_window.test(self.item, db_key):
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
                await self.moving_window.hit(self.item, db_key)
                # Returns normal response if the user did not go over the rate limit
                return func(request)

        return wrapper
