from functools import wraps
import json
from typing import Callable, Awaitable, Union, Optional
import asyncio
from aiohttp.web import Request, Response
from limits.storage import MemoryStorage


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


class RateLimitDecorator:
    """
    Decorator to rate limit requests in the aiohttp.web framework
    """

    def __init__(self, db: MemoryStorage, keyfunc: Callable, ratelimit: str, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
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
        self.error_handler = error_handler
        self.db = db

    def __call__(self, func: Callable) -> Awaitable:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            key = self.keyfunc(request)
            db_key = f"{key}:{str(id(func))}"

            if not self.db.check():
                self.db.reset()

            # Checks if the user's IP is in the set of exempt IPs
            if default_keyfunc(request) in self.exempt_ips:
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)

            # Returns a response if the number of calls exceeds the max amount of calls
            if self.db.get(db_key) >= self.calls:
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

            self.db.incr(key=db_key, expiry=self.period)
            # Returns normal response if the user did not go over the rate limit
            if asyncio.iscoroutinefunction(func):
                return await func(request)
            return func(request)

        return wrapper


class Limiter:
    """
    ```
    limiter = Limiter(keyfunc=your_keyfunc)

    @routes.get("/")
    @limiter.limit("5/1")
    def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(self, keyfunc: Callable, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.error_handler = error_handler
        self.db = MemoryStorage()

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None, error_handler: Optional[Union[Callable, Awaitable]] = None) -> Callable:
        def wrapper(func: Callable) -> Awaitable:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return RateLimitDecorator(keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips, error_handler=_error_handler, db=self.db)(func)
        return wrapper

