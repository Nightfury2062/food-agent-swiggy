# Food Agent

A terminal food-ordering concierge for Swiggy in India, built with the OpenAI Agents SDK, an OpenAI-compatible LLM endpoint (Gemini by default), and Swiggy's Food MCP server.

The agent can search restaurants and menus, build real Swiggy carts from returned menu payloads, parse the cart quote, audit the final payable amount against the requested budget, and present up to three matching options.

The application defaults to **dry-run mode**, so `DRY_RUN=true` does not place a real order.

## Features

* Searches Swiggy restaurants and menus through dedicated menu-scout agents.
* Builds carts in Python from the exact menu item/cart payload returned by the scout.
* Parses item total, delivery charges, taxes/charges, adjustments, and final payable amount.
* Audits final price, budget, vegetarian requirements, and scout-vs-cart item-total consistency.
* Keeps short-term conversation state and stores persistent preferences, feedback, and successfully placed orders in SQLite.
* Uses an embedding-backed local RAG store for nutrition lookup and past-order/feedback recall.
* Prints per-turn model/tool usage and timing information.
* Records OpenTelemetry traces in `traces.log`.

## Requirements

Use Python 3.11 or later.

The project expects the dependencies listed in `requirements.txt`.

## Setup

Create and activate a virtual environment.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root.

### Minimal configuration

```env
GEMINI_API_KEY=your_gemini_key
SWIGGY_ACCESS_TOKEN=your_swiggy_access_token
MODEL=gemini-3.5-flash-lite
DRY_RUN=true
```

`SWIGGY_ACCESS_TOKEN` is required even in dry-run mode because the application authenticates to Swiggy's Food MCP server before starting.

The model configuration uses these variables:

```env
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL=gemini-3.5-flash-lite
SMART_MODEL=
FAST_MODEL=
FAST_BASE_URL=
LLM_API_KEY=
GEMINI_API_KEY=
EMBED_MODEL=gemini-embedding-001
MAX_PARALLEL_LLM=2
```

`SMART_MODEL` overrides `MODEL` for the main concierge model. `FAST_MODEL` controls the scout model. `FAST_BASE_URL` can be used to send the fast role to a local OpenAI-compatible server. `LLM_API_KEY` is supported as an alternative API-key variable when `GEMINI_API_KEY` is not set.

`ORDER_TOOL_NAME` controls the live Swiggy order tool and defaults to:

```env
ORDER_TOOL_NAME=place_food_order
```

Never commit `.env` because it contains credentials.

## Build the nutrition index

The nutrition lookup uses a local SQLite-backed embedding index. When the nutrition dataset is available at `data/nutrition.csv`, build or rebuild the index with:

```bash
python build_index.py
```

This step is needed for nutrition lookup data. The application can otherwise still run, but an empty nutrition index will return no nutrition matches.

## Run

Start the terminal agent with:

```bash
python main.py
```

On startup the application reports whether it is running in dry-run or live mode.

Example:

```text
you> I want non veg options from Taco Bell under 400 to my saved Delhi address
```

Use:

```text
exit
```

or:

```text
quit
```

to leave the application.

## How it works

### 1. Address and request

The concierge first uses the saved `default_address_id` preference when available. Otherwise it can query the available addresses, ask the user to choose one, and save that choice.

It also collects the craving, budget, and vegetarian/non-vegetarian requirement. The budget is treated as the **maximum final payable amount**, not just the menu subtotal.

### 2. Menu scouting

The concierge calls `find_meal_options` with up to three search terms.

The scout agents:

1. Search Swiggy restaurants.
2. Search menus for promising restaurants.
3. Select candidate item combinations whose estimated item subtotal stays below the configured heuristic.
4. Preserve required `menu_item_id`, quantity, variants, `variantsV2`, and add-on payloads when present.
5. Return only candidate data derived from Swiggy tool results.

The system does not invent restaurant names, menu items, or prices.

### 3. Cart construction

Python, rather than the LLM, clears the current Swiggy cart and calls `update_food_cart` using the candidate's exact cart payload.

The cart-building code treats cart construction as a separate verification step and does not trust an LLM-generated claim that a cart was created successfully.

### 4. Quote parsing and auditing

The cart response is parsed into:

* restaurant
* item total
* delivery fee
* taxes and charges
* other adjustments
* final payable amount
* offer/discount-related notes
* ETA from the menu candidate

The resulting quote is audited before it is presented.

A candidate can be rejected for conditions such as:

* final total above the requested budget
* a non-vegetarian item when vegetarian-only was requested
* a significant mismatch between scout item prices and the cart item total
* cart construction or cart parsing failure

### 5. Presenting results

The concierge presents the audited options with the restaurant, items, pricing breakdown, final total, and ETA.

The user-facing agent is instructed not to claim that a restaurant is unavailable merely because cart construction, parsing, auditing, or another downstream step failed. A restaurant is considered unavailable only when restaurant search explicitly finds no deliverable match.

### 6. Ordering

The prototype currently supports **Cash on Delivery only**.

When the user selects an option, the application rebuilds the cart immediately before ordering and checks the new final price against the previously quoted price.

A price change greater than ₹5 causes the order flow to stop and asks the user to review the new amount.

Before a live order is submitted, the terminal displays the live cart response and requires explicit confirmation:

```text
Type YES to place this order:
```

When the current cart is above the saved budget, an additional terminal override is required.

With:

```env
DRY_RUN=true
```

the application records the attempted order as a dry run and does **not** call the configured live Swiggy order tool.

To enable live ordering:

```env
DRY_RUN=false
```

Live ordering should only be enabled when the Swiggy account, access token, payment configuration, and configured order tool are ready for real transactions.

## Tool access and safety

The application uses separate Swiggy MCP connections:

* **Scout connection:** `search_restaurants`, `search_menu`
* **Concierge connection:** `get_addresses`, `get_payment_options`, `track_food_order`, `get_food_orders`
* **Unrestricted Python connection:** used by the Python-side cart/order orchestration

The unrestricted connection is not exposed directly to the LLM as an MCP server. The Python-side order flow is also protected by explicit payment-method checks, cart rebuilding, price validation, and terminal confirmation.

## Memory and RAG

Persistent data is stored in `memory.db`.

The application stores:

* user preferences
* feedback
* successful order records
* dry-run order records
* embedding-backed documents for nutrition, orders, and feedback

Short-term conversation history is compacted between turns so older, large tool outputs can be trimmed while recent conversation state is retained.

## Diagnostics

Compile all Python files without executing them:

```bash
python -m compileall -q .
```

Useful generated files include:

```text
memory.db
traces.log
```

Cart-building failures are returned with diagnostic stages such as:

```text
flush_failed
update_failed
cart_fetch_failed
cart_empty_after_update
cart_parse_failed
```

The diagnostic response also retains relevant Swiggy response text and the cart payload when available.

Each turn prints model/tool timing information, including model-call counts, token usage, and per-tool timing.

## Environment variables

| Variable              | Purpose                                                         | Default                           |
| --------------------- | --------------------------------------------------------------- | --------------------------------- |
| `GEMINI_API_KEY`      | API key for the default Gemini-compatible endpoint              | —                                 |
| `SWIGGY_ACCESS_TOKEN` | Swiggy Food MCP authentication                                  | —                                 |
| `MODEL`               | Main model fallback                                             | `gemini-3.5-flash-lite`           |
| `SMART_MODEL`         | Main concierge model override                                   | value of `MODEL`                  |
| `FAST_MODEL`          | Scout model                                                     | value of `SMART_MODEL`            |
| `LLM_BASE_URL`        | OpenAI-compatible base URL for the main model                   | Gemini OpenAI-compatible endpoint |
| `LLM_API_KEY`         | Alternative LLM API-key variable                                | `local` fallback                  |
| `FAST_BASE_URL`       | Optional separate OpenAI-compatible endpoint for the fast model | main client                       |
| `EMBED_MODEL`         | Embedding model for RAG                                         | `gemini-embedding-001`            |
| `MAX_PARALLEL_LLM`    | Maximum concurrent scout LLM calls                              | `2`                               |
| `DRY_RUN`             | Prevents live order submission when `true`                      | `true`                            |
| `ORDER_TOOL_NAME`     | Swiggy live order tool name                                     | `place_food_order`                |

## Current limitations

* Only Cash on Delivery is supported by the order flow.
* Swiggy menu variants and mandatory add-ons must be represented by the exact cart payload returned by menu search; incomplete variant/add-on payloads can cause cart construction to fail.
* The scout intentionally targets candidate item totals below the final budget using a heuristic, so this is not an exhaustive optimizer for every possible combination.
* The application maintains one process-wide session object for the current terminal session rather than a multi-user/session store.
* Nutrition quality depends on the contents of `data/nutrition.csv` and whether the nutrition index has been built.
* The cart parser is format-sensitive to the textual structure returned by Swiggy MCP responses.

## Project structure

```text
agent_def.py       # Main concierge agent and instructions
build_index.py     # Builds the nutrition embedding index
cartparse.py       # Cart response parsing and deterministic auditing
config.py          # Environment configuration
main.py            # Terminal application entry point
mcp_servers.py     # Allowlisted and raw Swiggy MCP connections
memory.py          # Persistent preferences, orders, feedback, history compaction
models.py          # OpenAI-compatible model clients and token accounting
rag.py             # Embedding storage, search, and nutrition indexing
schemas.py         # Item, Candidate, Quote, and session models
subagents.py       # Menu scouts, cart construction, and option discovery
swiggy_auth.py     # Swiggy access-token loading
telemetry.py       # OpenTelemetry bridge and tracing
tools.py            # Nutrition, memory, and order tools
```

## Important behavior

The agent should never claim that an order was placed unless the live Swiggy order call reports success.

Likewise, a failed cart build, failed parse, failed audit, or downstream diagnostic is not by itself evidence that a restaurant is unavailable.
