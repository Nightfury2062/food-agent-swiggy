import asyncio
import time, telemetry, models
from agents import Runner, RunHooks
from agents.exceptions import MaxTurnsExceeded
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
            telemetry.bridge.reset()
            models.usage_log.clear()
            t0 = time.time()
            
            try:
                result = await Runner.run(agent, history, max_turns=30, hooks=LogHooks())
                u = models.usage_summary()
                print(f"[stats] {telemetry.bridge.stats['model_calls']} model calls | {u['prompt']} prompt tok "
                    f"({u['cached']} cached) | {u['completion']} out | {time.time()-t0:.1f}s | "
                    f"tools: {telemetry.bridge.stats['tool_seconds']}")
            except MaxTurnsExceeded:
                print("\nagent> Hit the step limit. Try a narrower request.\n")
                history.pop()
                continue
            print(f"\nagent> {result.final_output}\n")
            history = result.to_input_list()


asyncio.run(main())