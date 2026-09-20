import csv
import json
import math
import os
import sqlite3
from models import client

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")   # confirm in AI Studio
DB = "memory.db"


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, text TEXT, vec TEXT)")
    return c


async def embed(texts: list[str]) -> list[list[float]]:
    r = await client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in r.data]


async def add_doc(source: str, text: str):
    [v] = await embed([text])
    with _conn() as c:
        c.execute("INSERT INTO docs(source, text, vec) VALUES (?,?,?)", (source, text, json.dumps(v)))


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) + 1e-9)


async def search(query: str, sources: list[str], k: int = 3):
    [q] = await embed([query])
    marks = ",".join("?" * len(sources))
    with _conn() as c:
        rows = c.execute(f"SELECT text, vec FROM docs WHERE source IN ({marks})", sources).fetchall()
    scored = sorted(((_cos(q, json.loads(v)), t) for t, v in rows), reverse=True)[:k]
    return [(round(s, 3), t) for s, t in scored]


async def index_nutrition(path="data/nutrition.csv"):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    with _conn() as c:
        c.execute("DELETE FROM docs WHERE source='nutrition'")
    for i in range(0, len(rows), 20):
        batch = rows[i:i + 20]
        texts = [f"{r['dish']} | serving: {r['serving']} | {r['kcal']} kcal | protein {r['protein_g']} g | "
                 f"carbs {r['carbs_g']} g | fat {r['fat_g']} g" for r in batch]
        vecs = await embed(texts)
        with _conn() as c:
            c.executemany("INSERT INTO docs(source, text, vec) VALUES ('nutrition', ?, ?)",
                          [(t, json.dumps(v)) for t, v in zip(texts, vecs)])