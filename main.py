import asyncio
from agents import Runner, RunHooks
from agents.exceptions import MaxTurnsExceeded
import models  # noqa: F401  (sets up Gemini + disables tracing)
from agent_def import build_agent
from mcp_servers import swiggy_server


class LogHooks(RunHooks):
    async def on_tool_start(self, context, agent, tool):
        print(f"  [tool] {tool.name}")

    async def on_tool_end(self, context, agent, tool, result):
        print(f"  [result] {str(result)[:200]}\n")


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
            try:
                result = await Runner.run(agent, history, max_turns=30, hooks=LogHooks())
            except MaxTurnsExceeded:
                print("\nagent> Hit the step limit. Try a narrower request.\n")
                history.pop()
                continue
            print(f"\nagent> {result.final_output}\n")
            history = result.to_input_list()


asyncio.run(main())