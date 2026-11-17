"""Mealie import and recipe photos, with a small backup built like the real one (Mealie 3.x)."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import main

WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24

R1 = "aaaaaaaa-0000-0000-0000-000000000001"  # ids appear with dashes in folder names, without in database.json
R2 = "aaaaaaaa-0000-0000-0000-000000000002"
R3 = "aaaaaaaa-0000-0000-0000-000000000003"


def nodash(i):
    return i.replace("-", "")


def backup(extra_files=None) -> bytes:
    database = {
        "users": [{"id": "u1", "full_name": "Christian", "username": "tntdruid", "password": "secret-hash"}],
        "ingredient_units": [{"id": "un1", "name": "gram", "abbreviation": "g", "use_abbreviation": True},
                             {"id": "un2", "name": "dl", "abbreviation": "", "use_abbreviation": False}],
        "ingredient_foods": [{"id": "f1", "name": "hvedemel"}, {"id": "f2", "name": "mælk"}],
        "recipes": [
            {"id": nodash(R1), "name": "Mealie-pandekager", "description": "Tynde", "created_at": "2024-08-27T18:02:57",
             "recipe_servings": 4.0, "recipe_yield_quantity": 0.0, "total_time_seconds": None,
             "prep_time_seconds": 600, "perform_time_seconds": 1200, "org_url": "https://example.com/p",
             "last_made": "2025-05-04T21:59:59", "user_id": "u1"},
            {"id": nodash(R2), "name": "Mealie-grød", "description": "", "created_at": "2024-09-01T08:00:00",
             "recipe_servings": 0.0, "recipe_yield_quantity": 2.0, "last_made": "2025-01-02T10:00:00", "user_id": "u1"},
            # Mealie's own copy of the first recipe: same ingredients, " (1)" added to the name
            {"id": nodash(R3), "name": "Mealie-pandekager (1)", "created_at": "2024-08-28T18:02:57"},
        ],
        "recipes_ingredients": [
            {"recipe_id": nodash(R1), "position": 1, "quantity": 5, "unit_id": "un2", "food_id": "f2", "note": "kold"},
            {"recipe_id": nodash(R1), "position": 0, "quantity": 125.0, "unit_id": "un1", "food_id": "f1", "note": ""},
            {"recipe_id": nodash(R1), "position": 2, "quantity": 0, "note": "1 knivspids salt", "unit_id": None, "food_id": None},
            {"recipe_id": nodash(R2), "position": 0, "quantity": 0.5, "unit_id": "un2", "food_id": "f2", "note": "",
             "title": "Grød"},
            {"recipe_id": nodash(R3), "position": 0, "quantity": 125.0, "unit_id": "un1", "food_id": "f1", "note": ""},
            {"recipe_id": nodash(R3), "position": 1, "quantity": 5, "unit_id": "un2", "food_id": "f2", "note": "kold"},
            {"recipe_id": nodash(R3), "position": 2, "quantity": 0, "note": "1 knivspids salt"},
        ],
        "recipe_instructions": [
            {"recipe_id": nodash(R1), "position": 1, "title": "", "text": "Steg dem\n\ntynde."},
            {"recipe_id": nodash(R1), "position": 0, "title": "Dej", "text": "Pisk alt sammen."},
        ],
        "categories": [{"id": "c1", "name": "Morgenmad"}],
        "recipes_to_categories": [{"recipe_id": nodash(R1), "category_id": "c1"},
                                  {"recipe_id": nodash(R2), "category_id": "c1"}],
        "tags": [{"id": "t1", "name": "Søndag"}],
        "recipes_to_tags": [{"recipe_id": nodash(R1), "tag_id": "t1"}],
        "recipe_timeline_events": [
            {"recipe_id": nodash(R1), "user_id": "u1", "event_type": "system", "subject": "Opskrift oprettet",
             "timestamp": "2024-08-27T18:02:57"},
            {"recipe_id": nodash(R1), "user_id": "u1", "event_type": "comment", "subject": "Christian lavede denne",
             "timestamp": "2025-04-01T21:59:59"},
            {"recipe_id": nodash(R1), "user_id": "u1", "event_type": "comment", "subject": "Christian lavede denne",
             "timestamp": "2025-05-04T21:59:59"},
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("database.json", json.dumps(database))
        z.writestr("data/.secret", "do-not-read")
        z.writestr(f"data/recipes/{R1}/images/original.webp", WEBP)
        z.writestr(f"data/recipes/{R1}/images/tiny-original.webp", WEBP)
        z.writestr(f"data/recipes/{R2}/images/original.webp", b"not an image")
        for name, data in (extra_files or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def imported(client):
    r = client.post("/api/import/mealie", content=backup(), headers={"Content-Type": "application/zip"})
    assert r.status_code == 200, r.text
    return r.json()


def by_title(client, title):
    return next(r for r in client.get("/api/recipes").json() if r["title"] == title)


def test_import_summary(imported):
    assert imported["imported"] == 2
    assert imported["skipped"] == ["Mealie-pandekager (1)"]  # Mealie's duplicate copy
    assert imported["images"] == 1
    assert imported["cooked"] == 3  # two "made this" events + last_made on the recipe without events
    assert imported["image_errors"] == ["Mealie-grød: Billedet skal være JPEG, PNG, WebP eller GIF"]


def test_recipe_fields(client, imported):
    r = by_title(client, "Mealie-pandekager")
    assert r["description"] == "Tynde"
    assert r["servings"] == 4
    assert r["minutes"] == 30  # prep + perform time
    assert r["source_url"] == "https://example.com/p"
    assert r["ingredients"] == ["125 g hvedemel", "5 dl mælk, kold", "1 knivspids salt"]  # sorted by position
    assert r["steps"] == ["Dej: Pisk alt sammen.", "Steg dem tynde."]
    assert r["tags"] == ["Morgenmad", "Søndag"]
    g = by_title(client, "Mealie-grød")
    assert g["servings"] == 2  # from the yield when servings is empty
    assert g["ingredients"] == ["0,5 dl mælk"]  # Danish decimal comma


def test_made_events_become_cooked_history(client, imported):
    r = by_title(client, "Mealie-pandekager")
    assert r["times_cooked"] == 2  # the "system" event doesn't count
    assert r["last_cooked"] == 1746395999  # 2025-05-04T21:59:59 UTC
    recent = [x for x in client.get("/api/stats").json()["recent"] if x["title"] == "Mealie-pandekager"]
    assert all(x["user_name"] == "Christian" for x in recent)
    assert by_title(client, "Mealie-grød")["times_cooked"] == 1  # from last_made


def test_imported_photo_is_served(client, imported):
    r = by_title(client, "Mealie-pandekager")
    assert r["image"]
    img = client.get(f"/api/recipes/{r['id']}/image")
    assert img.status_code == 200 and img.content == WEBP and img.headers["content-type"] == "image/webp"
    assert by_title(client, "Mealie-grød")["image"] is None


def test_importing_again_adds_nothing(client, imported):
    r = client.post("/api/import/mealie", content=backup()).json()
    assert r["imported"] == 0 and r["cooked"] == 0
    assert set(r["skipped"]) == {"Mealie-pandekager", "Mealie-grød", "Mealie-pandekager (1)"}


@pytest.mark.parametrize("data, message", [
    (b"not a zip", "ikke en zip-fil"),
    (b"PK\x05\x06" + b"\x00" * 18, "database.json mangler"),  # an empty zip
])
def test_invalid_backup_is_rejected(client, data, message):
    r = client.post("/api/import/mealie", content=data)
    assert r.status_code == 400 and message in r.json()["detail"]


def test_upload_replace_and_remove_photo(client):
    made = client.post("/api/recipes", json={"title": "Fotoret"}).json()
    rid = made["id"]
    assert client.get(f"/api/recipes/{rid}/image").status_code == 404

    r = client.put(f"/api/recipes/{rid}/image", content=WEBP, headers={"Content-Type": "image/webp"})
    assert r.status_code == 200 and r.json()["image"] == f"{rid}.webp"
    # a PNG replaces the WebP, and the old file goes away
    r = client.put(f"/api/recipes/{rid}/image", content=PNG, headers={"Content-Type": "image/png"})
    assert r.json()["image"] == f"{rid}.png"
    assert client.get(f"/api/recipes/{rid}/image").content == PNG
    assert not (main.images.folder() / f"{rid}.webp").exists()

    assert client.put(f"/api/recipes/{rid}/image", content=b"<svg/>").status_code == 400
    assert client.delete(f"/api/recipes/{rid}/image").json()["image"] is None
    assert not (main.images.folder() / f"{rid}.png").exists()


def test_deleting_recipe_deletes_its_photo(client):
    rid = client.post("/api/recipes", json={"title": "Slettes med foto"}).json()["id"]
    client.put(f"/api/recipes/{rid}/image", content=PNG)
    client.delete(f"/api/recipes/{rid}")
    assert not (main.images.folder() / f"{rid}.png").exists()


def test_old_database_gets_image_column(tmp_path):
    """A database from 0.1.0 has no image column; connecting must add it."""
    import sqlite3

    import db
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.execute("CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',"
                " servings INTEGER, minutes INTEGER, ingredients TEXT NOT NULL DEFAULT '[]', steps TEXT NOT NULL DEFAULT '[]',"
                " tags TEXT NOT NULL DEFAULT '[]', source_url TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL,"
                " updated_at INTEGER NOT NULL)")
    con.commit()
    con.close()
    current = db._conn
    try:
        db.connect(old)
        assert "image" in {r["name"] for r in db.query("PRAGMA table_info(recipes)")}
    finally:
        db._conn = current
