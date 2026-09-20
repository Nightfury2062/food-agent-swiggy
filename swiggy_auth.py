import os
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
 

def get_swiggy_access_token() -> str:
    # TODO: replace with the real OAuth flow from the Swiggy Builders docs.
    # For now, paste a token into .env. Tokens expire, so refresh when calls fail.
    return os.environ["SWIGGY_ACCESS_TOKEN"]

async def main():
    token = get_swiggy_access_token()  # your OAuth helper
 
    swiggy_food = MCPServerStreamableHttp(
        params={
            "url": "https://mcp.swiggy.com/food",
            "headers": {"Authorization": f"Bearer {token}"},
        },
    )
    
    agent = Agent(
        name="FoodOrderingAgent",
        instructions="Help users order food on Swiggy. Always call get_addresses first.",
        mcp_servers=[swiggy_food],
    )
    
    await swiggy_food.connect()
    result = await Runner.run(agent, "Order biryani to my home address.")
    print(result.final_output)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())