from functools import wraps
import time
from collections import defaultdict
from aiohttp import web
import json
from typing import Callable
import asyncio
import functools


async def __run_func_async(func: Callable, args: list = None, loop: asyncio.AbstractEventLoop = None):
    args = tuple(args) if args is not None else tuple()
    loop = loop or asyncio.get_event_loop()
    r = await loop.run_in_executor(None, functools.partial(func, *args))
    return r


now = lambda: time.monotonic() if hasattr(time, 'monotonic') else time.time()


class RateLimitDecorator(object):
    def __init__(self, keyfunc, ratelimit: str, exempt_ips: set = None):
        self.exempt_ips = exempt_ips if exempt_ips is not None else set()
        calls, period = ratelimit.split("/")
        calls = int(calls)
        period = int(period)
        self.period = period
        self.raise_on_limit = True
        self.keyfunc = keyfunc
        self.calls = calls
        self.last_reset = defaultdict(now)
        self.num_calls = defaultdict(lambda: 0)

    def __call__(self, func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            key = await self.keyfunc(request)

            # Checks if the user's IP is in the set of exempt IPs
            if key in self.exempt_ips:
                return await func(request)

            # Checks if it is time to reset the number of calls
            if await self.__period_remaining(request) <= 0:
                try:
                    self.num_calls[key] = 0
                    self.last_reset[key] = await __run_func_async(now)
                except MemoryError:
                    self.num_calls[key] = 0
                    self.last_reset[key] = await __run_func_async(now)

            # Increments the number of calls by 1
            self.num_calls[key] += 1

            # Returns a JSON response if the number of calls exceeds the max amount of calls
            if self.num_calls[key] > self.calls:
                return web.Response(text=json.dumps({"Rate limit exceeded": f'{self.calls} request(s) per {self.period} second(s)'}), content_type="application/json", status=429)

            # Returns normal response if the user did not go over the ratelimit
            return await func(request, *args, **kwargs)
        return wrapper

    async def __period_remaining(self, request):
        """
        Gets the ammount of time remaining until the number of calls resets
        """
        key = await self.keyfunc(request)
        try:
            elapsed = await __run_func_async(now) - self.last_reset[key]
            return self.period - elapsed
        except MemoryError:
            await __run_func_async(self.last_reset.clear)
            elapsed = await __run_func_async(now) - self.last_reset[key]
            return self.period - elapsed


async def default_keyfunc(request):
    """
    Returns the user's IP
    """
    ip = request.headers.get(
        "X-Forwarded-For") or request.remote or "127.0.0.1"
    ip = (await __run_func_async(ip.split, [","]))[0]
    return ip

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
