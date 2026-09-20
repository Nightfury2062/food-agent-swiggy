import asyncio
from agents import Runner
from agent_def import build_agent
from mcp_servers import swiggy_server


async def main():
    async with swiggy_server(read_only=True) as ro, swiggy_server(read_only=False) as raw:
        agent = build_agent(ro, raw)
        history = []
        print("Food agent ready. Type 'exit' to quit.\n")
        while True:
            user = input("you> ").strip()
            if user.lower() in {"exit", "quit"}:
                break
            history.append({"role": "user", "content": user})
            result = await Runner.run(agent, history)
            print(f"\nagent> {result.final_output}\n")
            history = result.to_input_list()  # this is your short-term memory


asyncio.run(main())