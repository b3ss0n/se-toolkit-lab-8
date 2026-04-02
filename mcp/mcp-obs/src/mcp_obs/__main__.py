"""Entry point for running mcp_obs as a module."""
from mcp_obs.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
