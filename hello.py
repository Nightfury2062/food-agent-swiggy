import asyncio
from agents import Agent, Runner, function_tool
from models import get_model


@function_tool
def search_food(query: str) -> str:
    """Search restaurants for a dish."""
    return '[{"restaurant": "Biryani House", "item": "Chicken Biryani", "price": 320}]'


@function_tool
def get_cart_price(item: str, price: int) -> str:
    """Get final cart price including fees and GST."""
    return f'{{"item_total": {price}, "delivery": 40, "gst": 16, "final_total": {price + 56}}}'


agent = Agent(
    name="Hello",
    instructions="Find food, then get the cart price, then summarize.",
    model=get_model(),
    tools=[search_food, get_cart_price],
)


async def main():
    result = await Runner.run(agent, "I want biryani")
    for item in result.new_items:  # shows each tool call and result: this is the loop
        print(type(item).__name__)
    print(result.final_output)


asyncio.run(main())