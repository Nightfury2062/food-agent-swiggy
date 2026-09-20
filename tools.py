import asyncio
from agents import function_tool
from config import DRY_RUN, ORDER_TOOL_NAME
from memory import record_order
from rag import search
from schemas import SESSION
from subagents import build_cart


def build_order_args(payment_method: str, note: str = "") -> dict:
    normalized = "Cash" if payment_method.strip().lower() in {"cash", "cod", "cash on delivery"} else payment_method
    args = {"addressId": SESSION.address_id, "paymentMethod": normalized}
    if note:
        args["noteToRestaurant"] = note
    return args


@function_tool
async def lookup_nutrition(dish: str) -> str:
    """Approximate calories/protein for a dish from the local nutrition knowledge base (RAG)."""
    hits = await search(dish, ["nutrition"], k=3)
    return "\n".join(f"[match {s}] {t}" for s, t in hits) or "No nutrition data found."


@function_tool
async def recall_past_orders(query: str) -> str:
    """Search the user's past orders and feedback (e.g. 'that spicy paneer thing', 'my usual')."""
    hits = await search(query, ["order", "feedback"], k=4)
    return "\n".join(f"[match {s}] {t}" for s, t in hits) or "Nothing relevant in history."


def make_place_order_tool(raw):
    @function_tool
    async def place_order(option_number: int, payment_method: str, note_to_restaurant: str = "") -> str:
        """Place the order for an option previously returned by find_meal_options.
        Only Cash on Delivery is supported. The user is asked to confirm in the terminal."""
        if payment_method.strip().lower() not in {"cash", "cod", "cash on delivery"}:
            return "This prototype supports Cash on Delivery only. Ask the user to choose COD."
        entry = SESSION.options.get(option_number)
        if not entry:
            return "Unknown option. Call find_meal_options first."
        cand, quote = entry
        built, failure = await build_cart(cand, raw)  # Swiggy keeps one cart: rebuild it
        if not built:
            return f"Could not rebuild the cart. Order NOT placed. Diagnostic: {failure}"
        live, text = built
        if abs(live.final_total - quote.final_total) > 5:
            return (f"PRICE CHANGED: was Rs {quote.final_total}, now Rs {live.final_total}. "
                    "Tell the user and ask again. Order NOT placed.")
        print("\n=== ORDER CONFIRMATION (live cart from Swiggy, not written by the AI) ===")
        print(text)
        print(f"Payment: {payment_method}")
        if SESSION.budget and live.final_total > SESSION.budget:
            ans = await asyncio.to_thread(input, f"Over budget (Rs {SESSION.budget:.0f}). Type OVERRIDE: ")
            if ans.strip() != "OVERRIDE":
                return "User declined the over-budget order. Order NOT placed."
        if (await asyncio.to_thread(input, "Type YES to place this order: ")).strip() != "YES":
            return "User declined. Order NOT placed."
        if DRY_RUN:
            await record_order(live.restaurant, live.items, live.final_total, payment_method, True)
            return "DRY_RUN is on: order was NOT actually placed."
        if ORDER_TOOL_NAME.startswith("REPLACE"):
            return "ORDER_TOOL_NAME not configured. Order NOT placed."
        try:    # the order tool expects the payment picker data to have been fetched
            await raw.call_tool("get_payment_options", {"addressId": SESSION.address_id})
        except Exception:
            pass
        result = await raw.call_tool(ORDER_TOOL_NAME, build_order_args(payment_method, note_to_restaurant))
        out = "\n".join(c.text for c in result.content if hasattr(c, "text"))
        if getattr(result, "isError", False):
            return f"Swiggy rejected the order: {out}"
        await record_order(live.restaurant, live.items, live.final_total, payment_method, False)
        return out

    return place_order
