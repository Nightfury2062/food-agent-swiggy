import asyncio
import time
from contextlib import AsyncExitStack
import models
import telemetry
from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from agent_def import build_agent
from config import DRY_RUN
from memory import compact_history
from mcp_servers import CONCIERGE_TOOLS, PRICER_TOOLS, SCOUT_TOOLS, swiggy_server


async def main():
    async with AsyncExitStack() as stack:
        concierge = await stack.enter_async_context(swiggy_server(CONCIERGE_TOOLS))
        scout = await stack.enter_async_context(swiggy_server(SCOUT_TOOLS))
        pricer = await stack.enter_async_context(swiggy_server(PRICER_TOOLS))
        raw = await stack.enter_async_context(swiggy_server(None))

        for srv, allowed in ((concierge, CONCIERGE_TOOLS), (scout, SCOUT_TOOLS), (pricer, PRICER_TOOLS)):
            visible = {t.name for t in await srv.list_tools()}
            if not visible <= set(allowed):
                raise SystemExit(f"UNSAFE: agent can see unapproved tools: {visible - set(allowed)}")

        agent = build_agent(concierge, scout, pricer, raw)
        history = []
        print(f"Food agent ready. Mode: {'DRY RUN (no real orders)' if DRY_RUN else 'LIVE (real orders!)'}")
        print("Type 'exit' to quit.\n")
        while True:
            user = input("you> ").strip()
            if user.lower() in {"exit", "quit"}:
                break
            history.append({"role": "user", "content": user})
            telemetry.bridge.reset()
            models.usage_log.clear()
            t0 = time.time()
            try:
                result = await Runner.run(agent, history, max_turns=15)
            except MaxTurnsExceeded:
                print("\nagent> Hit the step limit. Try a narrower request.\n")
                history.pop()
                continue
            except Exception as e:
                print("\nSwiggy token expired: run python get_token.py\n" if "401" in str(e) else f"\nError: {e}\n")
                history.pop()
                continue
            u, s = models.usage_summary(), telemetry.bridge.stats
            print(f"\nagent> {result.final_output}\n")
            print(f"[stats] {u['calls']} model calls | {u['prompt']} prompt tok ({u['cached']} cached) | "
                  f"{u['completion']} out | {time.time()-t0:.1f}s | tools: {s['tool_seconds']}\n")
            history = compact_history(result.to_input_list())


asyncio.run(main())