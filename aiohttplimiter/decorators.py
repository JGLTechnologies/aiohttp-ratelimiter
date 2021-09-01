import asyncio
from functools import wraps
from math import floor
import time
import sys
import aiotools
from collections import defaultdict
from aiohttp.web import Request, middleware
from aiohttp import web
import json

class RateLimitException(Exception):
    def __init__(self, message, period_remaining, dec_inst):
        super(RateLimitException, self).__init__(message)
        self.period_remaining = period_remaining
        self.message = message
        self.inst = dec_inst

def now():
    return time.monotonic() if hasattr(time, 'monotonic') else time.time()

class RateLimitDecorator(object):
    def __init__(self, keyfunc, calls=5, period=1):
        self.clamped_calls = defaultdict(lambda: max(1, min(sys.maxsize, floor(calls))))
        self.period = period
        self.raise_on_limit = True
        self.keyfunc = keyfunc
        self.calls = calls
        self.last_reset = defaultdict(lambda: now())

        # Initialise the decorator state.
        self.num_calls = defaultdict(lambda: 0)

    def __call__(self, func):
        @wraps(func)
        async def wrapper(request):
            self.request = request
            # If the time window has elapsed then reset.
            if await self.__period_remaining(request) <= 0:
                self.num_calls[self.keyfunc(self.request)] = 0
                self.last_reset[self.keyfunc(self.request)] = await aiotools.run_func_async(now)

            # Increase the number of attempts to call the function.
            if self.num_calls[self.keyfunc(self.request)] > self.clamped_calls[self.keyfunc(self.request)]:
                    return web.Response(text=json.dumps({"Rate limit exceeded": f'{self.calls} requests per {self.period} seconds'}), content_type="application/json", status=429)

            self.num_calls[self.keyfunc(self.request)] += 1

            # If the number of attempts to call the function exceeds the
            # maximum then raise an exception.
            if self.num_calls[self.keyfunc(self.request)] > self.clamped_calls[self.keyfunc(self.request)]:
                    return web.Response(text=json.dumps({"Rate limit exceeded": f'{self.calls} requests per {self.period} seconds'}), content_type="application/json", status=429)

            return await func(request)
        return wrapper
        

    async def __period_remaining(self, request):
        elapsed = await aiotools.run_func_async(now) - self.last_reset[self.keyfunc(request)]
        return self.period - elapsed

def default_keyfunc(request):
    if x := request.headers.get("X-Forwarded-For") is None:
        return request.remote
    return x

limit = RateLimitDecorator

app = web.Application()
routes = web.RouteTableDef()

@routes.get("/")
@limit(period=5, calls=1, keyfunc=default_keyfunc)
async def test(request):
    return web.Response(text="test")

app.add_routes(routes)
web.run_app(app, port=81)
