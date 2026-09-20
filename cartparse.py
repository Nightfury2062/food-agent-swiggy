import re
from schemas import Candidate, Quote


async def cart_text(raw_server) -> str:
    res = await raw_server.call_tool("get_food_cart", {})   # if this errors, pass the args from tools.txt
    return "\n".join(c.text for c in res.content if hasattr(c, "text"))


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_cart(text: str) -> Quote | None:
    def grab(pat):
        m = re.search(pat, text, re.I)
        return _num(m.group(1)) if m else None

    item_total = grab(r"Item total:\s*₹\s*([\d,.]+)")
    to_pay = grab(r"TO PAY:\s*₹\s*([\d,.]+)")
    if item_total is None or to_pay is None:
        return None
    taxes = grab(r"Taxes & charges:\s*₹\s*([\d,.]+)") or 0.0
    m = re.search(r"Delivery:\s*(FREE|₹\s*([\d,.]+))", text, re.I)
    delivery = 0.0 if (not m or m.group(1).upper() == "FREE") else _num(m.group(2))
    rest = re.search(r"Restaurant:\s*(.+)", text)
    items = re.findall(r"^\s*-\s*(.+?)\s+—", text, re.M)
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
    cart = " ".join(quote.items).lower()
    for it in cand.items:
        if not _fuzzy_in(it.name, cart):
            problems.append(f"item missing from real cart: {it.name}")
    claimed = sum(i.price * i.qty for i in cand.items)
    if claimed and abs(claimed - quote.item_total) / claimed > 0.10:
        problems.append(f"scout price Rs {claimed} != cart item total Rs {quote.item_total}")
    return problems