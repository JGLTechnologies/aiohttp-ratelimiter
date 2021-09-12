from functools import wraps
import time
from aiohttp import web
from collections import defaultdict
import json
from typing import Callable, Awaitable, Union
import asyncio
from .utils import MemorySafeDict


now = lambda: time.time()


class RateLimitDecorator:
    """
    Decorator to ratelimit requests in the aiohttp.web framework
    """
    def __init__(self, last_reset: MemorySafeDict, num_calls: MemorySafeDict, keyfunc: Awaitable, ratelimit: str, exempt_ips: set = None, middleware_count: int = 0):
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

    def __call__(self, func):
        @wraps(func)
        async def wrapper(request):
            self.func = func
            func_key = id(func)
            key = await self.keyfunc(request)

            if self.last_reset.get(func_key) is None:
                self.last_reset[func_key] = MemorySafeDict(now, main=self.last_reset)

            if self.num_calls.get(func_key) is None:
                self.num_calls[func_key] = MemorySafeDict(lambda: 0, main=self.num_calls)

            # Checks if the user's IP is in the set of exempt IPs
            if key in self.exempt_ips:
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)

            # Checks if it is time to reset the number of calls
            if await self.__period_remaining(request) <= 0:
                self.num_calls[func_key][key] = 0
                self.last_reset[func_key][key] = now()

            # Increments the number of calls by 1
            self.num_calls[func_key][key] += 1

            # Returns a JSON response if the number of calls exceeds the max amount of calls
            if self.num_calls[func_key][key] > self.calls:
                response = json.dumps({"Rate limit exceeded": f'{self._calls} request(s) per {self.period} second(s)'})
                return web.Response(text=response, content_type="application/json", status=429)

            # Returns normal response if the user did not go over the ratelimit
            if asyncio.iscoroutinefunction(func):
                return await func(request)
            return func(request)
        return wrapper

    async def __period_remaining(self, request):
        """
        Gets the ammount of time remaining until the number of calls resets
        """
        func_key = id(self.func)
        key = await self.keyfunc(request)
        elapsed = now() - self.last_reset[func_key][key]
        return self.period - elapsed


async def default_keyfunc(request):
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
        return web.Response(text="Hello World")
    ```
    """
    def __init__(self, keyfunc: Awaitable, exempt_ips: set = None, middleware_count: int = 0, max_memory: Union[int, float] = 1):
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.middleware_count = middleware_count
        self.last_reset = MemorySafeDict(max_memory=max_memory/2)
        self.num_calls = MemorySafeDict(max_memory=max_memory/2)

    def limit(self, ratelimit: str, keyfunc: Awaitable = None, exempt_ips: set = None, middleware_count: int = None):
        def wrapper(func: Callable):
            _middleware_count = middleware_count or self.middleware_count
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            return RateLimitDecorator(keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips, middleware_count=_middleware_count, num_calls=self.num_calls, last_reset=self.last_reset)(func)
        return wrapper

"""
app = web.Application()
routes = web.RouteTableDef()

# This endpoint can only be requested one time per second per IP address.
@routes.get("/")
@RateLimitDecorator(ratelimit="1/1", keyfunc=default_keyfunc)
async def test(request):
    return web.Response(text="test")

app.add_routes(routes)
web.run_app(app)
"""