import os
from dotenv import load_dotenv
load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
ORDER_TOOL_NAME = os.getenv("ORDER_TOOL_NAME", "place_food_order")
ORDER_TOOLS = [ORDER_TOOL_NAME]          # kept so current tools.py still imports
MAX_PARALLEL_LLM = int(os.getenv("MAX_PARALLEL_LLM", "2"))   # free-tier friendly