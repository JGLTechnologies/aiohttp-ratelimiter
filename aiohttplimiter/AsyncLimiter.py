import asyncio
from typing import Callable, Dict, Optional, Type
from .utils import MemorySafeDict
from aiohttp import web

from aiolimiter.compat import current_task, get_running_loop


class AsyncLimiter:
    max_rate: float  #: The configured `max_rate` value for this limiter.
    time_period: float  #: The configured `time_period` value for this limiter.

    def __init__(self, max_rate: float, keyfunc: Callable, max_memory: float, time_period: float = 60) -> None:
        self.max_rate = max_rate
        self.time_period = time_period
        self._rate_per_sec = max_rate / time_period
        self._level = MemorySafeDict(default=lambda: 0.0, max_memory=max_memory/2)
        self._last_check = MemorySafeDict(default=lambda: 0.0, max_memory=max_memory/2)
        self.keyfunc = keyfunc
        # queue of waiting futures to signal capacity to
        self._waiters: Dict[asyncio.Task, asyncio.Future] = {}

    def _leak(self, request: web.Request) -> None:
        """Drip out capacity from the bucket."""
        loop = get_running_loop()
        if self._level[self.keyfunc(request)]:
            # drip out enough level for the elapsed time since
            # we last checked
            elapsed = loop.time() - self._last_check[self.keyfunc(request)]
            decrement = elapsed * self._rate_per_sec
            self._level[self.keyfunc(request)] = max(self._level[self.keyfunc(request)] - decrement, 0)
        self._last_check[self.keyfunc(request)] = loop.time()

    def has_capacity(self, request: web.Request, amount: float = 1) -> bool:
        """Check if there is enough capacity remaining in the limiter

        :param amount: How much capacity you need to be available.

        """
        self._leak(request)
        requested = self._level[self.keyfunc(request)] + amount
        # if there are tasks waiting for capacity, signal to the first
        # there there may be some now (they won't wake up until this task
        # yields with an await)
        if requested < self.max_rate:
            for fut in self._waiters.values():
                if not fut.done():
                    fut.set_result(True)
                    break
        return self._level[self.keyfunc(request)] + amount <= self.max_rate

    async def acquire(self, request: web.Request, amount: float = 1) -> None:
        """Acquire capacity in the limiter.

        If the limit has been reached, blocks until enough capacity has been
        freed before returning.

        :param amount: How much capacity you need to be available.
        :exception: Raises :exc:`ValueError` if `amount` is greater than
           :attr:`max_rate`.

        """
        if amount > self.max_rate:
            raise ValueError("Can't acquire more than the maximum capacity")

        loop = get_running_loop()
        task = current_task(loop)
        assert task is not None
        while not self.has_capacity(amount=amount, request=request):
            # wait for the next drip to have left the bucket
            # add a future to the _waiters map to be notified
            # 'early' if capacity has come up
            fut = loop.create_future()
            self._waiters[task] = fut
            try:
                await asyncio.wait_for(
                    asyncio.shield(fut), 1 / self._rate_per_sec * amount, loop=loop
                )
            except asyncio.TimeoutError:
                pass
            fut.cancel()
        self._waiters.pop(task, None)

        self._level[self.keyfunc(request)] += amount

        return None
