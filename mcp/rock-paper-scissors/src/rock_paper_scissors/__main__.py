"""Entry point for the rock-paper-scissors Agent App."""

import asyncio

from .server import run


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
