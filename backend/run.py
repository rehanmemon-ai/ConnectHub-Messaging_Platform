import asyncio
import selectors
import sys

import uvicorn


async def serve() -> None:
    """Serve ConnectHub on loopback using its existing FastAPI entry point."""
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="none",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    if sys.platform == "win32":

        def loop_factory() -> asyncio.AbstractEventLoop:
            return asyncio.SelectorEventLoop(selectors.SelectSelector())

        with asyncio.Runner(loop_factory=loop_factory) as runner:
            runner.run(serve())
        return
    asyncio.run(serve())


if __name__ == "__main__":
    main()
