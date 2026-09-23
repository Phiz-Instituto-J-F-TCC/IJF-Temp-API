import asyncio

import uvicorn
from uvicorn.config import Config
from uvicorn.server import Server


async def serve() -> None:
    config = Config("app.main:app", host="127.0.0.1", port=8000)
    server = Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(serve(), loop_factory=asyncio.SelectorEventLoop)
