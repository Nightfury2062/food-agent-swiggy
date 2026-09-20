import os
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("MODEL", "gemini-3.6-flash")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Fill this after Step 2 with the real tool name(s) that place an order.
ORDER_TOOLS = ["place_food_order"]