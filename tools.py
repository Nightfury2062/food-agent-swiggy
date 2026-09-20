import json
from agents import function_tool
from config import DRY_RUN, ORDER_TOOLS


@function_tool
def verify_price_math(
    item_total: float,
    discounts: float,
    delivery_fee: float,
    platform_fee: float,
    taxes: float,
    final_total: float,
) -> str:
    """Check that the price breakdown adds up to the final total. Call this on every cart before showing it to the user."""
    expected = item_total - discounts + delivery_fee + platform_fee + taxes
    diff = round(final_total - expected, 2)
    return "OK" if abs(diff) < 1 else f"MISMATCH: expected {expected}, platform says {final_total} (diff {diff})"


def make_place_order_tool(raw_server):
    """raw_server is an unfiltered connection. Only this function can order, and only after a human types YES."""

    @function_tool
    async def place_order(summary: str, arguments_json: str) -> str:
        """Place the order. summary: plain-English recap with restaurant, items, final total and address.
        arguments_json: JSON arguments for the platform's order tool. The user is asked to confirm."""
        print("\n=== ORDER CONFIRMATION ===")
        print(summary)
        answer = input("Type YES to place this order: ").strip()
        if answer != "YES":
            return "User declined. Order NOT placed."
        if DRY_RUN:
            return "DRY_RUN is on, so the order was NOT actually placed."
        result = await raw_server.call_tool(ORDER_TOOLS[0], json.loads(arguments_json))
        return str(result)

    return place_order