"""Checks that run on every push, so a broken version never reaches Home Assistant's store."""
import time

import pytest
from fastapi.testclient import TestClient

import main
import recipes


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.mark.parametrize("path", ["meta", "recipes", "recipes?q=æg", "recipes?tag=vegetar", "tags", "stats", "stats?start=0"])
def test_endpoint_answers(client, path):
    assert client.get(f"/api/{path}").status_code == 200


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "Opskrifter" in r.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/icon.svg").status_code == 200


def test_create_update_delete(client):
    r = client.post("/api/recipes", json={
        "title": "  Boller i karry ", "servings": "4", "minutes": "",
        "ingredients": "500 g kødfars\n\n1 løg\n", "steps": ["Rul bollerne", " ", "Kog dem"], "tags": "Dansk, dansk, Klassiker",
    })
    assert r.status_code == 201
    made = r.json()
    assert made["title"] == "Boller i karry"
    assert made["servings"] == 4 and made["minutes"] is None
    assert made["ingredients"] == ["500 g kødfars", "1 løg"]
    assert made["steps"] == ["Rul bollerne", "Kog dem"]
    assert made["tags"] == ["Dansk", "Klassiker"]  # duplicates in other case are dropped, first spelling wins
    assert made["times_cooked"] == 0

    r = client.put(f"/api/recipes/{made['id']}", json={**made, "title": "Boller i karry med ris"})
    assert r.json()["title"] == "Boller i karry med ris"

    assert client.delete(f"/api/recipes/{made['id']}").status_code == 204
    assert client.get(f"/api/recipes/{made['id']}").status_code == 404
    assert client.delete(f"/api/recipes/{made['id']}").status_code == 404


@pytest.mark.parametrize("data, message", [
    ({"title": "  "}, "titel"),
    ({"title": "X", "servings": "mange"}, "tal"),
    ({"title": "X", "minutes": 0}, "større end 0"),
])
def test_invalid_recipe_is_rejected(client, data, message):
    r = client.post("/api/recipes", json=data)
    assert r.status_code == 400 and message in r.json()["detail"]


def test_missing_recipe(client):
    assert client.get("/api/recipes/99999").status_code == 404
    assert client.put("/api/recipes/99999", json={"title": "X"}).status_code == 404
    assert client.post("/api/recipes/99999/cooked").status_code == 404


def test_cooked_counts_and_remembers_ha_user(client):
    made = client.post("/api/recipes", json={"title": "Tarteletter", "tags": "festmad"}).json()
    r = client.post(f"/api/recipes/{made['id']}/cooked", headers={"X-Remote-User-Display-Name": "Christian"})
    assert r.json()["times_cooked"] == 1
    s = client.get(f"/api/stats?start={int(time.time()) - 60}").json()
    assert s["recent"][0]["title"] == "Tarteletter"
    assert s["recent"][0]["user_name"] == "Christian"
    assert {"tag": "festmad", "times": 1} in s["tags"]


def test_search_matches_ingredients_and_all_words(client):
    titles = [r["title"] for r in client.get("/api/recipes?q=kokosmælk").json()]
    assert titles == ["Thai rød karry"]
    assert client.get("/api/recipes?q=kokosmælk frikadeller").json() == []


def test_tag_filter_ignores_case(client):
    titles = {r["title"] for r in client.get("/api/recipes?tag=VEGETAR").json()}
    assert titles == {"Linsesuppe", "Shakshuka"}


def test_stats_from_demo_data(client):
    s = client.get("/api/stats").json()
    assert s["cooked"] > 0
    assert s["top"][0]["times"] >= s["top"][-1]["times"]
    assert s["forgotten"][0]["title"] == "Shakshuka" and s["forgotten"][0]["last_cooked"] is None


def test_deleting_a_recipe_removes_its_history(client):
    made = client.post("/api/recipes", json={"title": "Engangsret"}).json()
    client.post(f"/api/recipes/{made['id']}/cooked")
    client.delete(f"/api/recipes/{made['id']}")
    assert "Engangsret" not in [r["title"] for r in recipes.stats()["recent"]]
