from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter
from swiggy_auth import get_swiggy_access_token

SCOUT_TOOLS = ["search_restaurants", "search_menu"]
PRICER_TOOLS = ["update_food_cart", "flush_food_cart", "fetch_food_coupons", "apply_food_coupon"]
CONCIERGE_TOOLS = ["get_addresses", "get_payment_options", "track_food_order", "get_food_orders"]

def swiggy_server(allowed: list[str] | None = None) -> MCPServerStreamableHttp:
    """allowed=None gives an unfiltered connection: ONLY code (never an LLM) may use it."""
    extra = {}
    if allowed is not None:
        extra["tool_filter"] = create_static_tool_filter(allowed_tool_names=allowed)
    return MCPServerStreamableHttp(
        name="swiggy-food",
        params={"url": "https://mcp.swiggy.com/food",
                "headers": {"Authorization": f"Bearer {get_swiggy_access_token()}"}},
        cache_tools_list=True, client_session_timeout_seconds=30, **extra)