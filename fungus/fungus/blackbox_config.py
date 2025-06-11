import importlib
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


def _load_config():
    anchor = "dynamics/config.yaml"
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / anchor).exists():
            root = parent
            break
    else:
        raise FileNotFoundError(f"Could not locate project root via anchor: {anchor}")
    with open(root / anchor, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), root


def resolve_path(alias):
    config, root = _load_config()
    path = config.get("paths", {}).get("aliases", {}).get(alias)
    if not path:
        raise KeyError(f"Alias '{alias}' not found in config.")
    return (root / path).resolve()


def resolve_import(name):
    config, _ = _load_config()
    dotted = config.get("imports", {}).get(name)
    if not dotted:
        raise KeyError(f"Import '{name}' not found in config.")
    module, attr = dotted.rsplit(".", 1)
    return getattr(importlib.import_module(module), attr)


def resolve_module(name):
    config, _ = _load_config()
    dotted = config.get("modules", {}).get(name)
    if not dotted:
        raise KeyError(f"Module '{name}' not found in config.")
    return importlib.import_module(dotted)


# === ROOT LOGGING FOLDER ===
BLACKBOX_PATH = os.path.join(os.getcwd(), ".blackbox")


# === GLOBAL LOGGING SETTINGS ===
BLACKBOX_SETTINGS = {
    "write_logs": True,
    "include_tracebacks": True,
    "retention_policy": {
        "max_age_days": 7,
        "max_size_mb": 5,
        "delete_after_days": 90,
        "max_disk_usage_gb": 300,
        "cleanup_target_gb": 250
    }
}


# === PATH MAP FOR DIFFERENT LOG TYPES ===
LOG_PATHS = {
    "token_index": os.path.join(BLACKBOX_PATH, "token_index"),
    "internal": os.path.join(BLACKBOX_PATH, "internal"),
    "dev": os.path.join(BLACKBOX_PATH, "dev"),
    "user_visible": os.path.join(BLACKBOX_PATH, "user_visible"),
    "memory": os.path.join(BLACKBOX_PATH, "memory"),
    "user_visible_zips": os.path.join(BLACKBOX_PATH, "user_visible_zips")
}


# === ENSURE ALL LOG FOLDERS EXIST ===
for path in LOG_PATHS.values():
    os.makedirs(path, exist_ok=True)


# === COMPATIBILITY: Fallback for legacy log writer ===
def current_utc_day_logfile():
    today_utc = datetime.now(ZoneInfo("UTC"))
