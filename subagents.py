import asyncio
import json
import re
from agents import Agent, Runner, function_tool
from cartparse import audit, cart_text, parse_cart
from config import MAX_PARALLEL_LLM
from models import get_model
from schemas import SESSION, Candidate

SCOUT_INSTRUCTIONS = """You are a menu scout for Swiggy. Input: search_term, budget_inr (final payable, taxes
add about 15 percent), veg_only, address_id. Call search_restaurants, then search_menu on at most 2 promising
restaurants. For each pick a small set of items whose item total is at most 80 percent of the budget. If
veg_only is true choose only items marked Veg. Use only ids and prices from tool results. Reply with ONLY JSON:
{"candidates":[{"restaurant_id":"","restaurant_name":"","eta":"","items":[{"id":"","name":"","price":0,"qty":1,"veg":true}]}]}"""

PRICER_INSTRUCTIONS = """You fill a Swiggy cart. Input is JSON with restaurant_id and items (id, qty). Call
flush_food_cart first, then update_food_cart with exactly those items. Do not change anything.
Reply with only DONE, or FAILED: <reason>."""


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


async def run_scout(term, budget, veg_only, address_id, scout_srv, sem):
    agent = Agent(name=f"scout-{term[:20]}", instructions=SCOUT_INSTRUCTIONS,
                  model=get_model("fast"), mcp_servers=[scout_srv])
    async with sem:
        res = await Runner.run(
            agent, f"search_term={term}\nbudget_inr={budget}\nveg_only={veg_only}\naddress_id={address_id}",
            max_turns=12)
    out = []
    for c in _json(res.final_output).get("candidates", []):
        try:
            out.append(Candidate(**c))
        except Exception:
            pass
    return out


async def build_cart(cand: Candidate, pricer_srv, raw):
    agent = Agent(name="pricer", instructions=PRICER_INSTRUCTIONS,
                  model=get_model("fast"), mcp_servers=[pricer_srv])
    payload = {"restaurant_id": cand.restaurant_id,
               "items": [{"id": i.id, "qty": i.qty} for i in cand.items]}
    res = await Runner.run(agent, json.dumps(payload), max_turns=8)
    if "FAILED" in (res.final_output or "").upper():
        return None
    text = await cart_text(raw)          # ground truth comes from Swiggy, parsed by code
    quote = parse_cart(text)
    if not quote:
        return None
    quote.eta = cand.eta
    return quote, text


def make_find_options_tool(scout_srv, pricer_srv, raw):
    @function_tool
    async def find_meal_options(search_terms: list[str], budget_inr: float,
                                veg_only: bool, address_id: str) -> str:
        """Find and price real meal options. search_terms: 2-3 dish or cuisine keywords.
        budget_inr: max FINAL payable amount. Returns up to 3 audited quotes built from real Swiggy carts."""
        sem = asyncio.Semaphore(MAX_PARALLEL_LLM)
        scouted = await asyncio.gather(
            *[run_scout(t, budget_inr, veg_only, address_id, scout_srv, sem) for t in search_terms[:3]],
            return_exceptions=True)
        cands, seen = [], set()
        for group in scouted:
            if isinstance(group, Exception):
                continue
            for c in group:
                if c.restaurant_id not in seen:
                    seen.add(c.restaurant_id)
                    cands.append(c)
        good, rejected = [], []
        for cand in cands[:4]:                       # sequential: one cart at a time
            try:
                built = await build_cart(cand, pricer_srv, raw)
            except Exception as e:
                rejected.append((cand.restaurant_name, f"error: {e}"))
                continue
            if not built:
                rejected.append((cand.restaurant_name, "could not build cart"))
                continue
            quote, _ = built
            problems = audit(cand, quote, budget_inr, veg_only)
            if problems:
                rejected.append((cand.restaurant_name, "; ".join(problems)))
            else:
                good.append((cand, quote))
        good.sort(key=lambda cq: cq[1].final_total)
        SESSION.budget = budget_inr
        SESSION.options = {i + 1: cq for i, cq in enumerate(good[:3])}
        return json.dumps({
            "options": [{"option": n, **q.model_dump()} for n, (_, q) in SESSION.options.items()],
            "rejected_by_auditor": [f"{n}: {why}" for n, why in rejected],
        }, ensure_ascii=False)

    return find_meal_options