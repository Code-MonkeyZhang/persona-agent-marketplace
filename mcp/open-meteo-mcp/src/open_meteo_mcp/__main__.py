"""Entry point for `python -m open_meteo_mcp` and the `open-meteo-mcp` console script."""

import asyncio

from .server import serve


def main() -> None:
    """Sync wrapper so the console script entry can run the async server."""
    asyncio.run(serve())


if __name__ == "__main__":
    main()
