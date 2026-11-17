"""Recipe photos, stored as files next to the database so they are part of backups and visible over Samba."""
from pathlib import Path
from typing import Optional

import db
from config import DB_DIR

MAX_BYTES = 15 * 1024 * 1024
MEDIA_TYPE = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


class InvalidImage(ValueError):
    pass


def folder() -> Path:
    path = DB_DIR / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def detect(data: bytes) -> Optional[str]:
    """The file type from the first bytes, so a wrong file name or content type can't fool it."""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


def _current(recipe_id: int) -> Optional[str]:
    rows = db.query("SELECT image FROM recipes WHERE id = ?", (recipe_id,))
    return rows[0]["image"] if rows else None


def path(recipe_id: int) -> Optional[Path]:
    name = _current(recipe_id)
    if name and (folder() / name).is_file():
        return folder() / name
    return None


def _delete_file(name: Optional[str]) -> None:
    if name:
        (folder() / name).unlink(missing_ok=True)


def save(recipe_id: int, data: bytes, now: int) -> str:
    if len(data) > MAX_BYTES:
        raise InvalidImage("Billedet er for stort (højst 15 MB)")
    ext = detect(data)
    if not ext:
        raise InvalidImage("Billedet skal være JPEG, PNG, WebP eller GIF")
    old = _current(recipe_id)
    name = f"{recipe_id}{ext}"
    (folder() / name).write_bytes(data)
    if old and old != name:
        _delete_file(old)
    db.execute("UPDATE recipes SET image = ?, updated_at = ? WHERE id = ?", (name, now, recipe_id))
    return name


def remove(recipe_id: int, now: int) -> None:
    _delete_file(_current(recipe_id))
    db.execute("UPDATE recipes SET image = NULL, updated_at = ? WHERE id = ?", (now, recipe_id))


def delete_file_of(recipe_id: int) -> None:
    """For a recipe that is about to be deleted."""
    _delete_file(_current(recipe_id))
