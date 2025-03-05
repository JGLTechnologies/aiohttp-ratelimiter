import asyncio

from aiohttp import ClientSession
from aiohttp.web import Application, RouteTableDef, Request, Response, run_app
from aiohttplimiter import *

app = Application()
routes = RouteTableDef()

limiter = Limiter(default_keyfunc)
@routes.get("/")
@limiter.limit("5/second")
async def foo(request: Request) -> Response: return Response(text="Hello World")

app.add_routes(routes)

async def task() -> None:
    status = False
    url = f"http://localhost:8080/"
    async with ClientSession() as session:
        while not status:
            async with session.get(url) as response:
                status = response.status == 200
            await asyncio.sleep(1)
    print("done")


loop = asyncio.new_event_loop()
loop.create_task(task())
run_app(app, loop=loop)
