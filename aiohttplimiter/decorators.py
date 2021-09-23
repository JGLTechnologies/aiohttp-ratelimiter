from functools import wraps
import time
import json
from typing import Callable, Awaitable, Union
import asyncio
from typing import Optional
from aiohttp.web import Request, Response
from .utils import MemorySafeDict
from aiolimiter import AsyncLimiter


IntOrFloat = Union[int, float]
now = lambda: time.time()


class RateLimitDecorator:
    """
    Decorator to ratelimit requests in the aiohttp.web framework
    """
    def __init__(self, last_reset: MemorySafeDict, num_calls: MemorySafeDict, keyfunc: Callable, ratelimit: str, exempt_ips: Optional[set] = None, middleware_count: int = 0, total_limit: Optional[AsyncLimiter] = None) -> None:
        self.exempt_ips = exempt_ips or set()
        calls, period = ratelimit.split("/")
        self._calls = calls
        calls = int(calls) + middleware_count
        period = int(period)
        self.period = period
        self.keyfunc = keyfunc
        self.calls = calls
        self.last_reset = last_reset
        self.num_calls = num_calls
        self.total_limit = total_limit

    def __call__(self, func: Callable) -> Awaitable:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            if self.total_limit is None:
                self.func = func
                func_key = id(func)
                key = self.keyfunc(request)

                if self.last_reset.get(func_key) is None:
                    self.last_reset[func_key] = MemorySafeDict(default=now, main=self.last_reset)
                    self.last_reset.append_nested_dict(self.last_reset[func_key])

                if self.num_calls.get(func_key) is None:
                    self.num_calls[func_key] = MemorySafeDict(default=lambda: 0, main=self.num_calls)
                    self.num_calls.append_nested_dict(self.num_calls[func_key])

                # Checks if the user's IP is in the set of exempt IPs
                if key in self.exempt_ips:
                    if asyncio.iscoroutinefunction(func):
                        return await func(request)
                    return func(request)

                # Checks if it is time to reset the number of calls
                if self.__period_remaining(request) <= 0:
                    self.num_calls[func_key][key] = 0
                    self.last_reset[func_key][key] = now()

                # Increments the number of calls by 1
                self.num_calls[func_key][key] += 1

                # Returns a JSON response if the number of calls exceeds the max amount of calls
                if self.num_calls[func_key][key] > self.calls:
                    response = json.dumps({"Rate limit exceeded": f'{self._calls} request(s) per {self.period} second(s)'})
                    return Response(text=response, content_type="application/json", status=429)

                # Returns normal response if the user did not go over the ratelimit
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)
            else:
                async with self.total_limit:
                    self.func = func
                func_key = id(func)
                key = self.keyfunc(request)

                if self.last_reset.get(func_key) is None:
                    self.last_reset[func_key] = MemorySafeDict(default=now, main=self.last_reset)
                    self.last_reset.append_nested_dict(self.last_reset[func_key])

                if self.num_calls.get(func_key) is None:
                    self.num_calls[func_key] = MemorySafeDict(default=lambda: 0, main=self.num_calls)
                    self.num_calls.append_nested_dict(self.num_calls[func_key])

                # Checks if the user's IP is in the set of exempt IPs
                if key in self.exempt_ips:
                    if asyncio.iscoroutinefunction(func):
                        return await func(request)
                    return func(request)

                # Checks if it is time to reset the number of calls
                if self.__period_remaining(request) <= 0:
                    self.num_calls[func_key][key] = 0
                    self.last_reset[func_key][key] = now()

                # Increments the number of calls by 1
                self.num_calls[func_key][key] += 1

                # Returns a JSON response if the number of calls exceeds the max amount of calls
                if self.num_calls[func_key][key] > self.calls:
                    response = json.dumps({"Rate limit exceeded": f'{self._calls} request(s) per {self.period} second(s)'})
                    return Response(text=response, content_type="application/json", status=429)

                # Returns normal response if the user did not go over the ratelimit
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)
        return wrapper

    def __period_remaining(self, request: Request) -> IntOrFloat:
        """
        Gets the ammount of time remaining until the number of calls resets
        """
        func_key = id(self.func)
        key = self.keyfunc(request)
        elapsed = now() - self.last_reset[func_key][key]
        return self.period - elapsed


def default_keyfunc(request: Request) -> str:
    """
    Returns the user's IP
    """
    ip = request.headers.get(
        "X-Forwarded-For") or request.remote or "127.0.0.1"
    ip = ip.split(".")[0]
    return ip

class Limiter:
    """
    This should be used if you plan on having the same settings for each endpoint

    ```
    limiter = Limiter(keyfunc=your_keyfunc, exempt_ips={"192.168.1.345"})

    @routes.get("/")
    @limiter.limit("5/1")
    def foo():
        return Response(text="Hello World")
    ```
    """
    def __init__(self, keyfunc: Callable, exempt_ips: Optional[set] = None, middleware_count: int = 0, max_memory: Optional[IntOrFloat] = None, total_limit: Optional[IntOrFloat] = None) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.middleware_count = middleware_count
        self.total_limit = total_limit
        self.last_reset = MemorySafeDict(max_memory=max_memory/2 if max_memory is not None else None)
        self.num_calls = MemorySafeDict(max_memory=max_memory/2 if max_memory is not None else None)

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None, middleware_count: int = None) -> Callable:
        def wrapper(func: Callable) -> RateLimitDecorator:
            _middleware_count = middleware_count or self.middleware_count
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _total_limit = AsyncLimiter(self.total_limit, 1) if self.total_limit is not None else None
            return RateLimitDecorator(keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips, middleware_count=_middleware_count, num_calls=self.num_calls, last_reset=self.last_reset, total_limit=_total_limit)(func)
        return wrapper

"""
from aiohttp import web
from aiohttplimiter import default_keyfunc, Limiter

app = web.Application()
routes = web.RouteTableDef()
limiter = Limiter(keyfunc=default_keyfunc, max_memory=.5)

@routes.get("/")
@limiter.limit(ratelimit="5/1")
def test(request):
    return web.Response(text="test")

app.add_routes(routes)
web.run_app(app)
"""
