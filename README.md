<a href="https://jgltechnologies.com/discord">
<img src="https://discord.com/api/guilds/844418702430175272/embed.png">
</a>

# aiohttp-ratelimiter

This library allows you to add a rate limit to your aiohttp.web app.


Install from git
```
python -m pip install git+https://github.com/Nebulizer1213/aiohttp-ratelimiter
```

Install from pypi
```
python -m pip install aiohttp-ratelimiter
```

<br>


Example

```python
from aiohttplimiter import limit
from aiohttp import web

app = web.Application()
routes = web.RouteTableDef()

# This endpoint can only be requested one time per second per IP address.
@routes.get("/")
@limit(ratelimit="1/1", keyfunc=default_keyfunc)
async def test(request):
    return web.Response(text="test")

app.add_routes(routes)
web.run_app(app)
```



