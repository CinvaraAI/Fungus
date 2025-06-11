import gzip
import json
import os
import shutil
import time
import yaml
import importlib
from datetime import datetime
from pathlib import Path

from fungus.blackbox_config import LOG_PATHS, BLACKBOX_SETTINGS, BLACKBOX_PATH

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


# === Layer 1 Configuration ===
ARCHIVE_DIR = os.path.join(LOG_PATHS["internal"], "archive")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

DEFAULT_RETENTION = {
    "max_disk_usage_gb": 300,
    "cleanup_target_gb": 250
}


def compress_log_file(path):
    """Compress a .jsonl file to .gz format and delete the original."""
    fname = os.path.basename(path)
    compressed_path = os.path.join(ARCHIVE_DIR, fname + ".gz")
    try:
        with open(path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(path)
        return compressed_path
    except Exception as e:
        print(f"[RetentionManager] Compression failed: {path} – {e}")
        return None


def get_disk_usage_gb(path):
    """Recursively calculate disk usage in GB for a given path."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except Exception:
                continue
    return total / (1024 ** 3)


def list_log_files_by_age(path):
    """Return list of (path, mtime) tuples sorted by age ascending."""
    files = []
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            if full_path.endswith(".jsonl") and os.path.isfile(full_path):
                try:
                    files.append((full_path, os.path.getmtime(full_path)))
                except Exception as e:
                    print(f"[RetentionManager] Failed to stat file {full_path}: {e}")
    return sorted(files, key=lambda x: x[1])


def archive_due_to_disk_pressure(config):
    """Compress oldest logs to reduce disk usage when over quota."""
    usage = get_disk_usage_gb(BLACKBOX_PATH)
    if usage < config["max_disk_usage_gb"]:
        print(f"[RetentionManager] Disk usage OK: {usage:.2f} GB")
        return

    print(f"[RetentionManager] Disk usage {usage:.2f} GB exceeds {config['max_disk_usage_gb']} GB. Starting cleanup.")
    target_bytes = config["cleanup_target_gb"] * (1024 ** 3)
    archived = 0

    files = list_log_files_by_age(BLACKBOX_PATH)
    for path, _ in files:
        if path.endswith(".gz") or not path.endswith(".jsonl"):
            continue
        try:
            size = os.path.getsize(path)
            compressed = compress_log_file(path)
            if compressed:
                archived += size
            if archived >= target_bytes:
                break
        except Exception as e:
            print(f"[RetentionManager] Error compressing {path}: {e}")

    print(f"[RetentionManager] Compressed ~{archived / (1024 ** 3):.2f} GB of logs")


def run_retention_policy():
    print("[RetentionManager] Running policy check...")
    config = BLACKBOX_SETTINGS.get("retention_policy", DEFAULT_RETENTION)
    archive_due_to_disk_pressure(config)
    print("[RetentionManager] Complete.")


# === Alias for step execution ===
def archive_layer1():
    run_retention_policy()


if __name__ == "__main__":
    run_retention_policy()
