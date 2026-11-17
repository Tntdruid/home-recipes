"""Fill a database with demo recipes and some cooking history, for local runs and the tests.

    .venv/Scripts/python dev/seed_demo.py
"""
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATA_DIR", str(ROOT / "dev" / "data"))
os.environ.setdefault("DB_DIR", os.environ["DATA_DIR"])
sys.path.insert(0, str(ROOT / "home_recipes" / "app"))

import db  # noqa: E402
import recipes  # noqa: E402

DEMO = [
    {"title": "Frikadeller", "servings": 4, "minutes": 45, "tags": "dansk, hverdag, kød",
     "ingredients": "500 g hakket svine- og kalvekød\n1 løg\n1 æg\n1 dl mælk\n3 spsk mel\nSalt og peber",
     "steps": "Riv løget og rør det i kødet med æg, mælk og mel.\nSmag til med salt og peber.\nSteg frikadellerne ca. 6 min på hver side."},
    {"title": "Pasta carbonara", "servings": 2, "minutes": 20, "tags": "pasta, hverdag, hurtig",
     "ingredients": "200 g spaghetti\n100 g guanciale\n2 æggeblommer\n40 g pecorino\nSort peber",
     "steps": "Kog pastaen.\nSteg guanciale sprød.\nVend pasta, æggeblommer og ost sammen med lidt kogevand."},
    {"title": "Linsesuppe", "servings": 4, "minutes": 35, "tags": "vegetar, suppe",
     "ingredients": "2 dl røde linser\n1 løg\n2 gulerødder\n1 dåse hakkede tomater\n1 l grøntsagsbouillon\n1 tsk spidskommen",
     "steps": "Svits løg og gulerødder.\nTilsæt resten og kog 20 min.\nBlend suppen."},
    {"title": "Æblekage", "servings": 6, "minutes": 30, "tags": "dessert, dansk",
     "ingredients": "1 kg æbler\n150 g makroner\n2 dl piskefløde\nRibsgele",
     "steps": "Kog æblerne til grød.\nLag æblegrød og knuste makroner i en skål.\nPynt med flødeskum og ribsgele."},
    {"title": "Thai rød karry", "servings": 4, "minutes": 30, "tags": "asiatisk, kylling, stærk",
     "ingredients": "500 g kyllingebryst\n2 spsk rød karrypasta\n1 dåse kokosmælk\n1 peberfrugt\nFiskesauce\nBasilikum",
     "steps": "Steg karrypastaen i lidt olie.\nTilsæt kylling og steg den.\nHæld kokosmælk og grøntsager i og lad det simre 10 min."},
    {"title": "Shakshuka", "servings": 2, "minutes": 25, "tags": "vegetar, brunch, hurtig",
     "ingredients": "1 dåse hakkede tomater\n1 rød peberfrugt\n1 løg\n4 æg\n1 tsk paprika",
     "steps": "Svits løg og peberfrugt.\nTilsæt tomater og krydderier.\nLav fordybninger og knæk æggene i; læg låg på til de er stivnede."},
]


def main():
    db.connect()
    if db.query("SELECT COUNT(*) AS n FROM recipes")[0]["n"]:
        print("database already has recipes - nothing to do")
        return
    rng = random.Random(42)
    now = int(time.time())
    made = [recipes.create(r, now=now - 200 * 86400) for r in DEMO]
    weights = [6, 5, 3, 1, 4, 0]  # the last one is never cooked
    for day in range(180):
        if rng.random() < 0.7:
            r = rng.choices(made, weights)[0]
            recipes.mark_cooked(r["id"], rng.choice(["Christian", "Gæst", None]), now - day * 86400 - rng.randint(0, 3600))
    print(f"seeded {len(made)} recipes into {os.environ['DB_DIR']}")


if __name__ == "__main__":
    main()
