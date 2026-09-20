from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter
from swiggy_auth import get_swiggy_access_token

READ_ONLY_TOOLS = ["get_addresses", "search_restaurants", "search_menu",
                   "update_food_cart", "get_food_cart", "flush_food_cart",
                   "get_payment_options"]

def swiggy_server(read_only: bool = True) -> MCPServerStreamableHttp:
    extra = {}
    if read_only:
        extra["tool_filter"] = create_static_tool_filter(allowed_tool_names=READ_ONLY_TOOLS)
    return MCPServerStreamableHttp(
        name="swiggy-food",
        params={"url": "https://mcp.swiggy.com/food",
                "headers": {"Authorization": f"Bearer {get_swiggy_access_token()}"}},
        cache_tools_list=True, client_session_timeout_seconds=30, **extra)