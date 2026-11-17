"""Run the app locally against dev/data (fill it first with dev/seed_demo.py).

    .venv/Scripts/python dev/run_demo.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "home_recipes" / "app"
os.environ.setdefault("DATA_DIR", str(ROOT / "dev" / "data"))
os.environ.setdefault("DB_DIR", os.environ["DATA_DIR"])
os.chdir(APP)
sys.path.insert(0, str(APP))

import uvicorn  # noqa: E402

uvicorn.run("main:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8099)))
