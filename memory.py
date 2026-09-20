import sqlite3
import time
from agents import function_tool
import rag

DB = "memory.db"


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS prefs (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 ts REAL, restaurant TEXT, items TEXT, total REAL, payment TEXT, dry_run INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, note TEXT)")
    return c


@function_tool
def save_preference(key: str, value: str) -> str:
    """Remember a lasting preference, e.g. diet=vegetarian, default_address_id=<id>, usual_budget=300."""
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO prefs VALUES (?, ?)", (key, value))
    return f"Saved {key}={value}"


@function_tool
async def save_feedback(note: str) -> str:
    """Save the user's opinion about a meal or restaurant (e.g. 'too oily', 'loved the paneer')."""
    with _conn() as c:
        c.execute("INSERT INTO feedback(ts, note) VALUES (?, ?)", (time.time(), note))
    await rag.add_doc("feedback", note)
    return "Saved."


async def record_order(restaurant: str, items: list[str], total: float, payment: str, dry_run: bool):
    with _conn() as c:
        c.execute("INSERT INTO orders(ts, restaurant, items, total, payment, dry_run) VALUES (?,?,?,?,?,?)",
                  (time.time(), restaurant, "; ".join(items), total, payment, int(dry_run)))
    tag = " (dry run)" if dry_run else ""
    await rag.add_doc("order", f"{time.strftime('%Y-%m-%d')}: {restaurant} - {'; '.join(items)} - INR {total}{tag}")


def load_preferences_text() -> str:
    with _conn() as c:
        prefs = c.execute("SELECT key, value FROM prefs").fetchall()
        recent = c.execute("SELECT restaurant, items, total FROM orders WHERE dry_run=0 "
                           "ORDER BY id DESC LIMIT 3").fetchall()
    lines = [f"- {k}: {v}" for k, v in prefs] or ["- none yet"]
    if recent:
        lines.append("Recent orders: " + " | ".join(f"{r}: {i} (INR {t})" for r, i, t in recent))
    return "\n".join(lines)


def compact_history(items: list, keep_recent: int = 14) -> list:
    """Short-term memory: shrink old tool outputs (menus are huge) but keep the conversation intact."""
    cutoff = len(items) - keep_recent
    out = []
    for i, it in enumerate(items):
        if i < cutoff and isinstance(it, dict) and it.get("type") == "function_call_output":
            it = {**it, "output": str(it.get("output", ""))[:200] + " ...[trimmed]"}
        out.append(it)
    return out