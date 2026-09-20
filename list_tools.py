import asyncio
from mcp_servers import swiggy_server


async def main():
    async with swiggy_server(read_only=False) as server:
        for t in await server.list_tools():
            print(f"{t.name}\n   {(t.description or '')[:150]}\n")


asyncio.run(main())