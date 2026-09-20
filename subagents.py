import asyncio
import json
import re
from agents import Agent, Runner, function_tool
from cartparse import audit, cart_text, parse_cart, result_error, result_text
from config import MAX_PARALLEL_LLM
from models import get_model
from schemas import SESSION, Candidate

SCOUT_INSTRUCTIONS = """You are a menu scout for Swiggy. Input: search_term, budget_inr (final payable; taxes
and fees add about 15 percent), veg_only, address_id.
1. Call search_restaurants with query=<search_term> and addressId=<address_id>.
2. For at most 2 promising restaurants, call search_menu with query=<search_term>, addressId=<address_id>,
   restaurantIdOfAddedItem=<restaurant id>, and vegFilter=1 if veg_only is true, else 0.
3. Return one or two distinct candidate carts for each promising restaurant, whose item total is at most
   80 percent of the budget. Prefer items that need no variant or addon choices. Never return an item that
   has variations, variantsV2, or mandatory add-ons unless cart_item copies the exact required fields from
   search_menu. A cart_item must always contain menu_item_id and quantity; preserve variants, variantsV2,
   and addons verbatim when present.
Use only ids and prices from tool results. Reply with ONLY JSON:
{"candidates":[{"restaurant_id":"","restaurant_name":"","eta":"","items":[{"id":"","name":"","price":0,
"qty":1,"veg":true,"cart_item":{"menu_item_id":"","quantity":1}}]}]}"""

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


async def build_cart(cand: Candidate, raw):
    """Build and verify a cart in code, never trusting an LLM's claim of success."""
    payload = {"address_id": SESSION.address_id,
            "restaurant_id": cand.restaurant_id,
            "restaurant_name": cand.restaurant_name,
            "cart_items": [i.cart_item or {"menu_item_id": i.id, "quantity": i.qty}
                            for i in cand.items]}
    try:
        flushed = await raw.call_tool("flush_food_cart", {})
        if error := result_error(flushed):
            return None, {"stage": "flush_failed", "detail": error}
        updated = await raw.call_tool("update_food_cart", {
            "addressId": payload["address_id"],
            "restaurantId": payload["restaurant_id"],
            "cartItems": payload["cart_items"],
        })
        if error := result_error(updated):
            return None, {"stage": "update_failed", "detail": error, "payload": payload}
        update_text = result_text(updated)
        update_quote = parse_cart(update_text)
        # Swiggy's update response is the authoritative cart mutation result. In
        # CLI/MCP sessions, get_food_cart can return only an empty-widget message
        # even immediately after a successful update, so it cannot veto this quote.
        try:
            fetched_text = await cart_text(raw, SESSION.address_id, cand.restaurant_name)
        except Exception as exc:
            fetched_text = f"get_food_cart unavailable: {exc}"
    except Exception as exc:
        return None, {"stage": "cart_fetch_failed", "detail": str(exc), "payload": payload}
    fetched_quote = parse_cart(fetched_text)
    quote = fetched_quote or update_quote
    if not quote:
        stage = "cart_empty_after_update" if re.search(r"cart is empty", fetched_text, re.I) else "cart_parse_failed"
        return None, {
            "stage": stage, "cart_response": fetched_text[:1000],
            "update_response": update_text[:1500], "payload": payload,
        }
    quote.eta = cand.eta
    quote.restaurant = cand.restaurant_name or quote.restaurant
    return (quote, update_text), None


def make_find_options_tool(scout_srv, raw):
    @function_tool
    async def find_meal_options(search_terms: list[str], budget_inr: float,
                                veg_only: bool, address_id: str) -> str:
        """Find and price real meal options. search_terms: 2-3 dish or cuisine keywords.
        budget_inr: max FINAL payable amount. Returns up to 3 audited quotes built from real Swiggy carts."""
        SESSION.address_id = address_id
        sem = asyncio.Semaphore(MAX_PARALLEL_LLM)
        scouted = await asyncio.gather(
            *[run_scout(t, budget_inr, veg_only, address_id, scout_srv, sem) for t in search_terms[:3]],
            return_exceptions=True)
        cands, seen = [], set()
        for group in scouted:
            if isinstance(group, Exception):
                continue
            for c in group:
                # A restaurant can have several legitimate menu payloads. Keep
                # them separate so one bad variant choice cannot hide the whole
                # restaurant (especially common for burger combos).
                key = (c.restaurant_id, tuple(
                    json.dumps(i.cart_item or {"menu_item_id": i.id, "quantity": i.qty}, sort_keys=True)
                    for i in c.items
                ))
                if key not in seen:
                    seen.add(key)
                    cands.append(c)
        good, rejected = [], []
        for cand in cands[:6]:                       # sequential: one cart at a time
            try:
                built, failure = await build_cart(cand, raw)
            except Exception as e:
                rejected.append((cand.restaurant_name, f"error: {e}"))
                continue
            if not built:
                rejected.append((cand.restaurant_name, failure))
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
            "failures": [{"restaurant": n, "reason": why} for n, why in rejected],
        }, ensure_ascii=False)

    return find_meal_options
