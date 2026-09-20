from agents import Agent
from models import get_model
from tools import verify_price_math, make_place_order_tool
from memory import save_preference, load_preferences_text

INSTRUCTIONS = """
You are a food-ordering assistant for Swiggy.

Workflow:
1. Always call get_addresses first and confirm which address to use.
2. Search for options matching the user's craving and budget.
3. For your top 3 options, build the cart and get the FINAL price.
4. Call verify_price_math on each one. If it says MISMATCH, warn the user.
5. Present the 3 options as a short list: restaurant, items, discounts applied,
   delivery fee, GST/taxes, final total, ETA.
6. Never invent prices, offers or cart IDs. Use only tool results.
7. Only call place_order after the user explicitly picks an option.
"""


def build_agent(read_only_server, raw_server) -> Agent:
    return Agent(
        name="FoodOrderingAgent",
        # instructions=INSTRUCTIONS,
        model=get_model(),
        mcp_servers=[read_only_server],
        # tools=[verify_price_math, make_place_order_tool(raw_server)],
        instructions=INSTRUCTIONS + "\nKnown user preferences:\n" + load_preferences_text(),
        tools=[verify_price_math, save_preference, make_place_order_tool(raw_server)],
    )    