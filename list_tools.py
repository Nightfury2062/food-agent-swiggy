import asyncio
import json
from mcp_servers import swiggy_server


async def main():
    # None = unfiltered connection, so every tool (including the order tool) is listed
    async with swiggy_server(None) as server:
        tools = await server.list_tools()
        with open("tools.txt", "w", encoding="utf-8") as f:
            for t in tools:
                schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
                f.write(f"\n## {t.name}\n{(t.description or '')[:400]}\n")
                f.write(json.dumps(schema, indent=1, ensure_ascii=False)[:1500] + "\n")
        print(f"Wrote {len(tools)} tools to tools.txt")
        print("Tool names:", ", ".join(t.name for t in tools))


asyncio.run(main())