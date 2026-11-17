"""Import a Mealie backup (the zip from Mealie's Settings → Backups).

The zip holds database.json, one list of rows per database table, and the photos under
data/recipes/<recipe id>/images/. Only those are read; everything else in the zip is ignored.
Importing the same backup again adds nothing, because recipes that already exist are skipped.
"""
import io
import json
import logging
import re
import time
import zipfile
from datetime import datetime, timezone
from typing import Optional

import images
import recipes

log = logging.getLogger("mealie")

MAX_DATABASE_BYTES = 200 * 1024 * 1024
PHOTO = re.compile(r"(?:^|/)recipes/([0-9a-fA-F-]{32,36})/images/original\.(?:webp|jpe?g|png|gif)$")
COPY_SUFFIX = re.compile(r"\s*\(\d+\)$")  # Mealie names a second copy "Pizza (1)"


class InvalidBackup(ValueError):
    pass


def _id(value) -> str:
    """Mealie writes ids both with and without dashes."""
    return str(value or "").replace("-", "").lower()


def _timestamp(value) -> Optional[int]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:  # Mealie stores UTC without saying so
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _number(value) -> str:
    """350.0 -> "350", 0.5 -> "0,5" (Danish decimal comma); 0 or nothing -> ""."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0").replace(".", ",")


def _positive(value) -> Optional[int]:
    try:
        n = int(float(value or 0))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _by_recipe(rows) -> dict:
    out = {}
    for row in sorted(rows or [], key=lambda r: r.get("position") or 0):
        out.setdefault(_id(row.get("recipe_id")), []).append(row)
    return out


def _ingredient(row, units, foods) -> str:
    note = (row.get("note") or "").strip()
    unit = units.get(_id(row.get("unit_id")))
    food = foods.get(_id(row.get("food_id")))
    if not unit and not food:
        text = note or (row.get("original_text") or "").strip()
        qty = _number(row.get("quantity"))
        return f"{qty} {text}".strip() if text else qty
    line = " ".join(p for p in (_number(row.get("quantity")), unit, food) if p)
    return f"{line}, {note}" if note else line


def _step(row) -> str:
    text = " ".join(line.strip() for line in (row.get("text") or "").splitlines() if line.strip())
    title = (row.get("title") or "").strip()
    return f"{title}: {text}" if title and text else title or text


def _signature(title: str, ingredients: list) -> tuple:
    return COPY_SUFFIX.sub("", title).strip().lower(), tuple(i.lower() for i in ingredients)


def _unit_name(u) -> str:
    if u.get("use_abbreviation") and u.get("abbreviation"):
        return u["abbreviation"]
    return u.get("name") or ""


def read_backup(data: bytes) -> tuple:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise InvalidBackup("Filen er ikke en zip-fil")
    name = next((n for n in archive.namelist() if n.rsplit("/", 1)[-1] == "database.json"), None)
    if not name:
        raise InvalidBackup("Zip-filen er ikke en Mealie-backup (database.json mangler)")
    if archive.getinfo(name).file_size > MAX_DATABASE_BYTES:
        raise InvalidBackup("database.json er for stor")
    try:
        database = json.loads(archive.read(name))
    except ValueError:
        raise InvalidBackup("database.json kan ikke læses")
    if not isinstance(database, dict) or not isinstance(database.get("recipes"), list):
        raise InvalidBackup("Zip-filen er ikke en Mealie-backup (ingen opskrifter)")
    return archive, database


def import_backup(data: bytes) -> dict:
    archive, d = read_backup(data)
    units = {_id(u.get("id")): _unit_name(u) for u in d.get("ingredient_units") or []}
    foods = {_id(f.get("id")): f.get("name") or "" for f in d.get("ingredient_foods") or []}
    users = {_id(u.get("id")): u.get("full_name") or u.get("username") for u in d.get("users") or []}
    ingredients = _by_recipe(d.get("recipes_ingredients"))
    steps = _by_recipe(d.get("recipe_instructions"))
    events = _by_recipe(d.get("recipe_timeline_events"))

    labels = {}  # Mealie's categories and tags both become tags here
    for table, link_table, key in (("categories", "recipes_to_categories", "category_id"),
                                   ("tags", "recipes_to_tags", "tag_id")):
        names = {_id(r.get("id")): r.get("name") for r in d.get(table) or []}
        for link in d.get(link_table) or []:
            if names.get(_id(link.get(key))):
                labels.setdefault(_id(link.get("recipe_id")), []).append(names[_id(link.get(key))])

    photos = {}
    for entry in archive.namelist():
        m = PHOTO.search(entry)
        if m:
            photos[_id(m.group(1))] = entry

    existing = recipes.list_recipes()
    titles = {r["title"].lower() for r in existing}
    signatures = {_signature(r["title"], r["ingredients"]) for r in existing}
    result = {"imported": 0, "skipped": [], "cooked": 0, "images": 0, "image_errors": []}

    for m in d["recipes"]:
        mid = _id(m.get("id"))
        title = (m.get("name") or "").strip()
        if not title:
            continue
        lines = [i for i in (_ingredient(r, units, foods) for r in ingredients.get(mid, [])) if i]
        sig = _signature(title, lines)
        if title.lower() in titles or sig in signatures:
            result["skipped"].append(title)
            continue
        minutes = None
        seconds = _positive(m.get("total_time_seconds")) or (
            (_positive(m.get("prep_time_seconds")) or 0) + (_positive(m.get("perform_time_seconds")) or 0))
        if seconds:
            minutes = max(1, round(seconds / 60))
        made = recipes.create({
            "title": title,
            "description": m.get("description") or "",
            "servings": _positive(m.get("recipe_servings")) or _positive(m.get("recipe_yield_quantity")),
            "minutes": minutes,
            "ingredients": lines,
            "steps": [s for s in (_step(r) for r in steps.get(mid, [])) if s],
            "tags": labels.get(mid, []),
            "source_url": m.get("org_url") or "",
        }, now=_timestamp(m.get("created_at")) or int(time.time()))
        titles.add(title.lower())
        signatures.add(sig)
        result["imported"] += 1

        # "I made this" in Mealie is a timeline event of a user's own (not "system");
        # last_made covers recipes that were marked without one.
        cooked = [e for e in events.get(mid, []) if e.get("event_type") != "system" and _timestamp(e.get("timestamp"))]
        for e in cooked:
            recipes.mark_cooked(made["id"], users.get(_id(e.get("user_id"))), _timestamp(e["timestamp"]))
        if not cooked and _timestamp(m.get("last_made")):
            recipes.mark_cooked(made["id"], users.get(_id(m.get("user_id"))), _timestamp(m["last_made"]))
        result["cooked"] += len(cooked) or (1 if _timestamp(m.get("last_made")) else 0)

        if mid in photos:
            try:
                images.save(made["id"], archive.read(photos[mid]), made["updated_at"])
                result["images"] += 1
            except images.InvalidImage as e:
                result["image_errors"].append(f"{title}: {e}")
    log.info("mealie import: %s", {k: v if isinstance(v, int) else len(v) for k, v in result.items()})
    return result
