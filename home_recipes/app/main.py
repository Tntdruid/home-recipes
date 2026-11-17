import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
import images
import mealie
import recipes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")

STATIC = Path(__file__).parent / "static"
VERSION = "0.2.0"
MAX_IMPORT_BYTES = 1024 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    yield


app = FastAPI(lifespan=lifespan)


def ha_user(request: Request) -> Optional[str]:
    """Home Assistant's ingress proxy says who is looking at the page."""
    return request.headers.get("X-Remote-User-Display-Name") or request.headers.get("X-Remote-User-Name")


def found(recipe):
    if recipe is None:
        raise HTTPException(404, "Opskriften findes ikke")
    return recipe


def valid(fn, *args):
    try:
        return fn(*args)
    except recipes.InvalidRecipe as e:
        raise HTTPException(400, str(e))


@app.get("/api/meta")
def meta(request: Request):
    return {"version": VERSION, "ha_user": ha_user(request)}


@app.get("/api/recipes")
def list_recipes(q: str = "", tag: str = ""):
    return recipes.list_recipes(q, tag)


@app.post("/api/recipes", status_code=201)
def create_recipe(data: dict = Body(...)):
    return valid(recipes.create, data)


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    return found(recipes.get(recipe_id))


@app.put("/api/recipes/{recipe_id}")
def update_recipe(recipe_id: int, data: dict = Body(...)):
    return found(valid(recipes.update, recipe_id, data))


@app.delete("/api/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int):
    if not recipes.delete(recipe_id):
        raise HTTPException(404, "Opskriften findes ikke")


@app.post("/api/recipes/{recipe_id}/cooked")
def cooked(recipe_id: int, request: Request):
    return found(recipes.mark_cooked(recipe_id, ha_user(request)))


@app.get("/api/recipes/{recipe_id}/image")
def get_image(recipe_id: int):
    path = images.path(recipe_id)
    if not path:
        raise HTTPException(404, "Opskriften har intet billede")
    return FileResponse(path, media_type=images.MEDIA_TYPE[path.suffix], headers={"Cache-Control": "max-age=31536000"})


@app.put("/api/recipes/{recipe_id}/image")
async def put_image(recipe_id: int, request: Request):
    found(recipes.get(recipe_id))
    try:
        images.save(recipe_id, await request.body(), int(time.time()))
    except images.InvalidImage as e:
        raise HTTPException(400, str(e))
    return recipes.get(recipe_id)


@app.delete("/api/recipes/{recipe_id}/image")
def delete_image(recipe_id: int):
    found(recipes.get(recipe_id))
    images.remove(recipe_id, int(time.time()))
    return recipes.get(recipe_id)


@app.post("/api/import/mealie")
async def import_mealie(request: Request):
    """The body is the backup zip itself, so no form/multipart handling is needed."""
    data = await request.body()
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "Filen er for stor")
    try:
        return mealie.import_backup(data)
    except mealie.InvalidBackup as e:
        raise HTTPException(400, str(e))


@app.get("/api/tags")
def tags():
    return recipes.all_tags()


@app.get("/api/stats")
def stats(start: int = 0):
    return recipes.stats(start)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
