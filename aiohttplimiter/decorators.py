import asyncio
from functools import wraps
from math import floor
import time
import sys
import aiotools
from collections import defaultdict
from aiohttp import web
import json


def now():
    return time.monotonic() if hasattr(time, 'monotonic') else time.time()


class RateLimitDecorator(object):
    def __init__(self, keyfunc, ratelimit: str, sleep_while_limited: bool = False):
        calls, period = ratelimit.split("/")
        calls = int(calls)
        period = int(period)
        self.sleep_while_limited = sleep_while_limited
        self.clamped_calls = defaultdict(
            lambda: max(1, min(sys.maxsize, floor(calls))))
        self.period = period
        self.raise_on_limit = True
        self.keyfunc = keyfunc
        self.calls = calls
        self.last_reset = defaultdict(now)
        self.num_calls = defaultdict(lambda: 0)

    def __call__(self, func):
        @wraps(func)
        async def wrapper(request):
            self.request = request
            if await self.__period_remaining(request) <= 0:
                try:
                    self.num_calls[await self.keyfunc(self.request)] = 0
                    self.last_reset[await self.keyfunc(self.request)] = await aiotools.run_func_async(now)
                except MemoryError:
                    self.num_calls[await self.keyfunc(self.request)] = 0
                    self.last_reset[await self.keyfunc(self.request)] = await aiotools.run_func_async(now)

            self.num_calls[await self.keyfunc(self.request)] += 1

            if self.num_calls[await self.keyfunc(self.request)] > self.clamped_calls[await self.keyfunc(self.request)]:
                if not self.sleep_while_limited:
                    return web.Response(text=json.dumps({"Rate limit exceeded": f'{self.calls} request(s) per {self.period} second(s)'}), content_type="application/json", status=429)
                await asyncio.sleep(await self.__period_remaining(request))

            return await func(request)
        return wrapper

    async def __period_remaining(self, request):
        try:
            elapsed = await aiotools.run_func_async(now) - self.last_reset[await self.keyfunc(request)]
            return self.period - elapsed
        except MemoryError:
            await aiotools.run_func_async(self.last_reset.clear)
            elapsed = await aiotools.run_func_async(now) - self.last_reset[await self.keyfunc(request)]
            return self.period - elapsed


async def default_keyfunc(request):
    return request.headers.get("X-Forwarded-For") or request.remote

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
