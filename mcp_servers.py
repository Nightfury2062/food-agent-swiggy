from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter
from config import ORDER_TOOLS
from swiggy_auth import get_swiggy_access_token


def swiggy_server(read_only: bool = True) -> MCPServerStreamableHttp:
    """read_only=True hides order-placing tools from the LLM completely."""
    extra = {}
    if read_only:
        extra["tool_filter"] = create_static_tool_filter(blocked_tool_names=ORDER_TOOLS)

    return MCPServerStreamableHttp(
        name="swiggy-food",
        params={
            "url": "https://mcp.swiggy.com/food",
            "headers": {"Authorization": f"Bearer {get_swiggy_access_token()}"},
        },
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        **extra,
    )