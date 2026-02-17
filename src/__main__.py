"""Entry point for running the CLI as a module: python -m src.cli."""

from src.cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
