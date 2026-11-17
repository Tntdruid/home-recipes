"""Recipes and the log of when they were cooked."""
import json
import time
from typing import Optional

import db
import images


class InvalidRecipe(ValueError):
    pass


def _lines(value) -> list:
    """Accept a list or a block of text with one item per line; blank lines are dropped."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.splitlines()
    return [str(v).strip() for v in value if str(v).strip()]


def _tags(value) -> list:
    """Tags are matched case-insensitively, so "Pasta" and "pasta" become one tag (the first spelling wins)."""
    if isinstance(value, str):
        value = value.replace("\n", ",").split(",")
    seen, out = set(), []
    for tag in _lines(value):
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def _positive_int(value, name) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InvalidRecipe(f"{name} skal være et tal")
    if number <= 0:
        raise InvalidRecipe(f"{name} skal være større end 0")
    return number


def clean(data: dict) -> dict:
    title = str(data.get("title") or "").strip()
    if not title:
        raise InvalidRecipe("Opskriften mangler en titel")
    return {
        "title": title,
        "description": str(data.get("description") or "").strip(),
        "servings": _positive_int(data.get("servings"), "Antal personer"),
        "minutes": _positive_int(data.get("minutes"), "Tid"),
        "ingredients": _lines(data.get("ingredients")),
        "steps": _lines(data.get("steps")),
        "tags": _tags(data.get("tags")),
        "source_url": str(data.get("source_url") or "").strip(),
    }


def _row(r: dict) -> dict:
    for key in ("ingredients", "steps", "tags"):
        r[key] = json.loads(r[key])
    return r


_SELECT = """
SELECT r.*, COUNT(c.id) AS times_cooked, MAX(c.cooked_at) AS last_cooked
FROM recipes r LEFT JOIN cooked c ON c.recipe_id = r.id
"""


def list_recipes(q: str = "", tag: str = "") -> list:
    rows = [_row(r) for r in db.query(_SELECT + " GROUP BY r.id ORDER BY r.title COLLATE NOCASE")]
    if tag:
        rows = [r for r in rows if tag.lower() in (t.lower() for t in r["tags"])]
    for word in q.lower().split():
        rows = [r for r in rows if word in " ".join([r["title"], r["description"], *r["ingredients"], *r["tags"]]).lower()]
    return rows


def get(recipe_id: int) -> Optional[dict]:
    rows = db.query(_SELECT + " WHERE r.id = ? GROUP BY r.id", (recipe_id,))
    return _row(rows[0]) if rows else None


def _values(r: dict) -> tuple:
    return (r["title"], r["description"], r["servings"], r["minutes"], json.dumps(r["ingredients"], ensure_ascii=False),
            json.dumps(r["steps"], ensure_ascii=False), json.dumps(r["tags"], ensure_ascii=False), r["source_url"])


def create(data: dict, now: Optional[int] = None) -> dict:
    r = clean(data)
    now = now or int(time.time())
    cur = db.execute(
        "INSERT INTO recipes (title, description, servings, minutes, ingredients, steps, tags, source_url, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", _values(r) + (now, now))
    return get(cur.lastrowid)


def update(recipe_id: int, data: dict) -> Optional[dict]:
    r = clean(data)
    cur = db.execute(
        "UPDATE recipes SET title = ?, description = ?, servings = ?, minutes = ?, ingredients = ?, steps = ?, tags = ?,"
        " source_url = ?, updated_at = ? WHERE id = ?", _values(r) + (int(time.time()), recipe_id))
    return get(recipe_id) if cur.rowcount else None


def delete(recipe_id: int) -> bool:
    images.delete_file_of(recipe_id)
    return db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,)).rowcount > 0


def mark_cooked(recipe_id: int, user_name: Optional[str] = None, at: Optional[int] = None) -> Optional[dict]:
    if not get(recipe_id):
        return None
    db.execute("INSERT INTO cooked (recipe_id, cooked_at, user_name) VALUES (?, ?, ?)",
               (recipe_id, at or int(time.time()), user_name))
    return get(recipe_id)


def all_tags() -> list:
    counts = {}
    for r in list_recipes():
        for t in r["tags"]:
            counts.setdefault(t.lower(), [t, 0])[1] += 1
    return sorted(({"tag": t, "recipes": n} for t, n in counts.values()), key=lambda x: (-x["recipes"], x["tag"].lower()))


def stats(start: int = 0) -> dict:
    """What has been cooked since `start` (unix seconds)."""
    top = db.query(
        "SELECT r.id, r.title, COUNT(*) AS times FROM cooked c JOIN recipes r ON r.id = c.recipe_id"
        " WHERE c.cooked_at >= ? GROUP BY r.id ORDER BY times DESC, r.title COLLATE NOCASE LIMIT 10", (start,))
    recent = db.query(
        "SELECT r.id, r.title, c.cooked_at, c.user_name FROM cooked c JOIN recipes r ON r.id = c.recipe_id"
        " WHERE c.cooked_at >= ? ORDER BY c.cooked_at DESC LIMIT 10", (start,))
    tags = {}
    for row in db.query("SELECT r.tags FROM cooked c JOIN recipes r ON r.id = c.recipe_id WHERE c.cooked_at >= ?", (start,)):
        for t in json.loads(row["tags"]):
            tags.setdefault(t.lower(), [t, 0])[1] += 1
    total = db.query("SELECT COUNT(*) AS n, COUNT(DISTINCT recipe_id) AS d FROM cooked WHERE cooked_at >= ?", (start,))[0]
    # Recipes that have never been cooked, or not for the longest time: ideas for what to make next
    forgotten = db.query(
        "SELECT r.id, r.title, MAX(c.cooked_at) AS last_cooked FROM recipes r LEFT JOIN cooked c ON c.recipe_id = r.id"
        " GROUP BY r.id ORDER BY last_cooked IS NOT NULL, last_cooked, r.title COLLATE NOCASE LIMIT 5")
    return {
        "cooked": total["n"],
        "distinct_recipes": total["d"],
        "recipes_total": db.query("SELECT COUNT(*) AS n FROM recipes")[0]["n"],
        "top": top,
        "tags": sorted(({"tag": t, "times": n} for t, n in tags.values()), key=lambda x: -x["times"])[:10],
        "recent": recent,
        "forgotten": forgotten,
    }
