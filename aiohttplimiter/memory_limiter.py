from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from .limiter import BaseRateLimitDecorator
from typing import Callable, Optional, Union, Awaitable


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

    def __init__(self, keyfunc: Callable, exempt_ips: Optional[set] = None,
                 error_handler: Optional[Union[Callable, Awaitable]] = None) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.error_handler = error_handler
        self.db = MemoryStorage()
        self.moving_window = MovingWindowRateLimiter(self.db)

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None,
              error_handler: Optional[Union[Callable, Awaitable]] = None, path_id: str = None) -> Callable:
        def wrapper(func: Callable) -> Awaitable:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return BaseRateLimitDecorator(keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips,
                                      error_handler=_error_handler, db=self.db, path_id=path_id,
                                      moving_window=self.moving_window)(func)

        return wrapper

    async def reset(self):
        self.db.reset()
