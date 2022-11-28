from typing import Callable, Awaitable, Union, Optional, Any, Coroutine
import coredis
from aiohttp.web import Request, Response, View
from limits.aio.storage import RedisStorage
from .limiter import BaseRateLimitDecorator
from limits.aio.strategies import MovingWindowRateLimiter


class RedisLimiter:
    """
    ```
    limiter = RedisLimiter(keyfunc=your_keyfunc, uri="localhost:6379")
    @routes.get("/")
    @limiter.limit("5/1")
    def foo():
        return Response(text="Hello World")
    ```
    """

    def __init__(self, keyfunc: Callable, uri: str, exempt_ips: Optional[set] = None,
                 error_handler: Optional[Union[Callable, Awaitable]] = None,
                 connection_pool: Optional[coredis.ConnectionPool] = None, **options: Union[float, str, bool]) -> None:
        self.exempt_ips = exempt_ips or set()
        self.keyfunc = keyfunc
        self.db = RedisStorage(uri, connection_pool, **options)
        self.moving_window = MovingWindowRateLimiter(self.db)
        self.error_handler = error_handler

    def limit(self, ratelimit: str, keyfunc: Callable = None, exempt_ips: Optional[set] = None,
              error_handler: Optional[Union[Callable, Awaitable]] = None, path_id: str = None) -> Callable:
        def wrapper(func: Callable) -> Callable[[Union[Request, View]], Coroutine[Any, Any, Response]]:
            _exempt_ips = exempt_ips or self.exempt_ips
            _keyfunc = keyfunc or self.keyfunc
            _error_handler = self.error_handler or error_handler
            return BaseRateLimitDecorator(db=self.db, keyfunc=_keyfunc, ratelimit=ratelimit, exempt_ips=_exempt_ips,
                                          error_handler=_error_handler, path_id=path_id,
                                          moving_window=self.moving_window)(
                func)

        return wrapper
