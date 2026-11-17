"""Point the app at a throw-away data folder filled with the demo data, before any app module is imported."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "home_recipes" / "app"

DATA = tempfile.mkdtemp(prefix="home-recipes-test-")
os.environ["DATA_DIR"] = DATA
os.environ["DB_DIR"] = DATA

subprocess.run([sys.executable, str(ROOT / "dev" / "seed_demo.py")], check=True, env=os.environ, capture_output=True)
sys.path.insert(0, str(APP))
