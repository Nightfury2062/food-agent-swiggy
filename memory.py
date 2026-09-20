import sqlite3
from agents import function_tool

DB = "memory.db"


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS prefs (key TEXT PRIMARY KEY, value TEXT)")
    return c


@function_tool
def save_preference(key: str, value: str) -> str:
    """Remember a lasting user preference, e.g. diet=vegetarian, spice=high, usual_budget=400."""
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO prefs VALUES (?, ?)", (key, value))
    return f"Saved {key}={value}"


def load_preferences_text() -> str:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM prefs").fetchall()
    return "\n".join(f"- {k}: {v}" for k, v in rows) or "None yet."