"""Entry point for the pomodoro-timer Agent App."""

import asyncio

from .server import run


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
