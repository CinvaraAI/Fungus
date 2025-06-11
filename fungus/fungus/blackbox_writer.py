import os
import json
import yaml
import importlib
from datetime import datetime
from pathlib import Path

from fungus.blackbox_config import BLACKBOX_PATH, BLACKBOX_SETTINGS


# === Config Loader ===
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


# === Logging Functions ===
def _get_log_file_path(log_type, log_data):
    user_id = log_data.get("user_id", "anon")
    project_id = log_data.get("project_id", "unknown")
    task_id = log_data.get("task_id", "unknown")
    date = datetime.utcnow().strftime("%Y-%m-%d")

    folder = os.path.join(
        BLACKBOX_PATH,
        f"user_{user_id}",
        f"project_{project_id}",
        f"task_{task_id}",
        log_type
    )

    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{date}.jsonl")


def _safe_serialize(data):
    try:
        return json.dumps(data, ensure_ascii=False)
    except TypeError:
        def default(o):
            try:
                return repr(o)
            except Exception:
                return f"<unserializable:{type(o).__name__}>"
        return json.dumps(data, default=default, ensure_ascii=False)


def write_blackbox_log(log_type, log_data, visibility="internal"):
    if not BLACKBOX_SETTINGS.get("write_logs", True):
        return

    if "__ts__" not in log_data:
        log_data["__ts__"] = datetime.utcnow().isoformat()

    try:
        log_path = _get_log_file_path(log_type, log_data)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(_safe_serialize(log_data) + "\n")
    except Exception as e:
        fallback_dir = os.path.join(BLACKBOX_PATH, "internal")
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, "fallback.jsonl")

        fallback_entry = {
            "__ts__": datetime.utcnow().isoformat(),
            "__error__": str(e),
            "__original__": str(log_data)
        }

        with open(fallback_path, "a", encoding="utf-8") as f:
            f.write(_safe_serialize(fallback_entry) + "\n")
