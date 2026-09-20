# Food Agent

A terminal food-ordering concierge built with the OpenAI Agents SDK, Gemini through its OpenAI-compatible API, and Swiggy's Food MCP server.

The agent searches restaurants and menus, builds a real Swiggy cart, parses the final payable amount, and shows options that meet the requested budget. It starts in dry-run mode, so testing never places an order.

## Setup

Use Python 3.11 or later, create a virtual environment, and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_key
SWIGGY_ACCESS_TOKEN=your_swiggy_access_token
MODEL=gemini-3.5-flash-lite
DRY_RUN=true
```

Never commit `.env`; it contains API credentials.

## Run

```powershell
python main.py
```

Example:

```text
you> I want non veg options from Taco Bell under 400 to my saved Delhi address
```

Use `exit` or `quit` to leave the app.

## How it works

1. The concierge gets a saved delivery address and request details.
2. Menu scouts search Swiggy for restaurants and menu items.
3. Python, not an LLM, clears and updates the food cart using the candidate's exact item payload.
4. The update response is parsed as the authoritative quote. `get_food_cart` is checked as a best-effort follow-up because Swiggy's CLI widget endpoint can sometimes return an empty-cart message after a successful update.
5. Price, budget, and dietary checks audit each quote before it is shown.

The user-facing agent must never infer that a restaurant is unavailable merely because cart construction, parsing, or auditing fails. It can make that claim only when restaurant search returns no deliverable match.

## Safety

- `DRY_RUN=true` prevents `place_food_order` from being called.
- The assistant asks for terminal confirmation before a live order.
- Only the Python order path has access to the unrestricted Swiggy connection; LLM-facing connections use allowlisted tools.
- A real order currently supports Cash on Delivery only.

## Diagnostics

Each turn prints model/tool statistics and short tool results. Cart failures return a structured stage such as `update_failed`, `cart_empty_after_update`, or `cart_parse_failed`, with the relevant Swiggy response retained for debugging.

Useful checks:

```powershell
python -m compileall -q .
python list_tools.py
```

## Current limitation

The Taco Bell dry-run flow has been verified with a real cart quote: a non-veg combo priced at ₹374 for the saved Delhi address.

McDonald's search also finds the restaurant, but the current Swiggy menu candidate can return `Cart updated` followed by `Cart is empty`. The app reports this accurately as a cart-payload/cart-state problem rather than claiming McDonald's is unavailable. The next improvement is to capture and submit McDonald's required variant/add-on payloads exactly as returned by its menu response.
