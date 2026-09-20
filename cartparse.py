import re
from schemas import Candidate, Quote


def result_text(result) -> str:
    """Extract MCP text without assuming a particular result-content class."""
    return "\n".join(
        getattr(part, "text", str(part)) for part in (getattr(result, "content", None) or [])
    ).strip()


def result_error(result) -> str | None:
    """Return an actionable error from an MCP result, when one was reported."""
    text = result_text(result)
    if getattr(result, "isError", False):
        return text or "Swiggy returned an unspecified error"
    # Some MCP servers put semantic failures in text instead of setting isError.
    if re.search(r"\b(error|failed|invalid|unable to add|not available)\b", text, re.I):
        return text
    return None


async def cart_text(raw_server, address_id: str, restaurant_name: str = "") -> str:
    args = {"addressId": address_id}
    if restaurant_name:
        args["restaurantName"] = restaurant_name
    res = await raw_server.call_tool("get_food_cart", args)
    error = result_error(res)
    if error:
        raise RuntimeError(f"get_food_cart failed: {error}")
    return result_text(res)

def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_cart(text: str) -> Quote | None:
    def grab(pat):
        m = re.search(pat, text, re.I)
        return _num(m.group(1)) if m else None

    item_total = grab(r"item\s*total\s*:?\s*(?:₹|Rs\.?|INR)?\s*([\d,.]+)")
    to_pay = grab(r"(?:to\s*pay|total\s*payable|grand\s*total)\s*:?\s*(?:₹|Rs\.?|INR)?\s*([\d,.]+)")
    if item_total is None or to_pay is None:
        return None
    taxes = grab(r"(?:taxes?\s*(?:&|and)?\s*charges?|gst)\s*:?\s*(?:₹|Rs\.?|INR)?\s*([\d,.]+)") or 0.0
    m = re.search(r"delivery(?:\s*fee|\s*charges?)?\s*:\s*(FREE|₹\s*([\d,.]+)|Rs\.?\s*([\d,.]+))", text, re.I)
    delivery = 0.0 if (not m or m.group(1).upper() == "FREE") else _num(m.group(2) or m.group(3))
    rest = re.search(r"Restaurant:\s*(.+)", text)
    items = re.findall(r"^\s*[-•]\s*(.+?)(?:\s+[—–-]\s*|\s+×\s*\d+|$)", text, re.M)
    notes = [ln.strip() for ln in text.splitlines()
             if re.search(r"coupon|offer|discount|saved|% off", ln, re.I)][:3]
    return Quote(
        restaurant=rest.group(1).strip() if rest else "?", items=items,
        item_total=item_total, delivery_fee=delivery, taxes_and_charges=taxes,
        other_adjustments=round(to_pay - (item_total + delivery + taxes), 2),
        final_total=to_pay, notes=notes,
    )


def _fuzzy_in(name: str, text: str) -> bool:
    words = [w for w in re.findall(r"\w+", name.lower()) if len(w) > 2]
    return sum(w in text for w in words) >= max(1, len(words) // 2)


def audit(cand: Candidate, quote: Quote, budget: float, veg_only: bool) -> list[str]:
    """Deterministic auditor: catches wrong items, invented prices, budget and veg violations."""
    problems = []
    if budget and quote.final_total > budget:
        problems.append(f"over budget (Rs {quote.final_total} > Rs {budget})")
    if veg_only and any(i.veg is False for i in cand.items):
        problems.append("contains a non-veg item")
    # Cart widgets do not consistently expose item names. Price/budget checks are
    # hard failures; name differences must not make a real cart disappear.
    claimed = sum(i.price * i.qty for i in cand.items)
    if claimed and abs(claimed - quote.item_total) / claimed > 0.10:
        problems.append(f"scout price Rs {claimed} != cart item total Rs {quote.item_total}")
    return problems
