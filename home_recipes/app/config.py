"""Where the add-on keeps its data. Env vars override the Home Assistant paths for local dev and tests."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
# The add-on's public config folder (map: addon_config), visible as addon_configs/<slug> over Samba.
# Falls back to DATA_DIR when it isn't mounted, e.g. in local development.
DB_DIR = Path(os.environ.get("DB_DIR") or ("/config" if os.path.isdir("/config") else DATA_DIR))
