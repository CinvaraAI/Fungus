import importlib
import inspect
import json
import os
import threading
import yaml
from datetime import datetime
from pathlib import Path

from fungus.blackbox_config import LOG_PATHS

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


# === Tagging Engine ===
_seen_signatures = set()
_tag_lock = threading.Lock()

def _get_tag_path(file_name):
    return os.path.join(LOG_PATHS["internal"], file_name)

TAG_HISTORY_PATH = _get_tag_path("tag_history.jsonl")
TAG_MANIFEST_PATH = _get_tag_path("tag_manifest.yaml")
GPT_TAGS_PATH = _get_tag_path("telephone_generated_tags.yaml")

os.makedirs(LOG_PATHS["internal"], exist_ok=True)

_static_tag_rules = {}

def _load_yaml(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[TagEngine] Failed to load YAML from {path}: {e}")
        return {}

def _load_static_tag_rules():
    global _static_tag_rules
    if not _static_tag_rules:
        manifest_tags = _load_yaml(TAG_MANIFEST_PATH)
        telephone_tags = _load_yaml(GPT_TAGS_PATH)
        _static_tag_rules = {**manifest_tags, **telephone_tags}
    return _static_tag_rules

def _get_module_path(obj):
    try:
        mod = inspect.getmodule(obj)
        return mod.__name__ if mod else "unknown"
    except Exception:
        return "unknown"

def _get_file_path(obj):
    try:
        file = inspect.getfile(obj)
        return os.path.relpath(file)
    except Exception:
        return repr(obj)

def _generate_signature(obj):
    mod = _get_module_path(obj)
    name = getattr(obj, "__name__", "unknown")
    return f"{mod}.{name}"

def _record_signature_history(signature, tags):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "signature": signature,
        "tags": tags
    }
    try:
        with open(TAG_HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[TagEngine] Failed to write tag history: {e}")

def _apply_static_tags(ctx, result):
    tags = []
    rules = _load_static_tag_rules()

    for key, val in ctx.items():
        if key in rules:
            if isinstance(rules[key], list):
                tags.extend([f"{key}:{v}" for v in rules[key]])
            else:
                tags.append(f"{key}:{rules[key]}")

    if isinstance(result, dict):
        for key, val in result.items():
            if key in rules:
                tags.append(f"{key}:{val}")

    return tags

def tag_for_context(obj=None, ctx=None, result=None):
    ctx = ctx or {}
    tags = []

    tags.append(f"user:{ctx.get('user_id', 'anon')}")
    tags.append(f"task:{ctx.get('task_id', 'unknown')}")
    tags.append(f"session:{ctx.get('session_id', 'none')}")
    tags.append(f"step:{ctx.get('step', 'start')}")

    tags.extend(_apply_static_tags(ctx, result))

    if result and isinstance(result, dict):
        model = result.get("model")
        if model:
            tags.append(f"model:{model}")

    if obj:
        name = getattr(obj, "__name__", "unknown")
        mod = _get_module_path(obj)
        file = _get_file_path(obj)
        signature = _generate_signature(obj)

        if mod and ("tag_engine" in mod or "tag_engine" in file):
            return tags

        tags.extend([
            f"func:{name}",
            f"module:{mod}",
            f"file:{file}"
        ])

        with _tag_lock:
            if signature not in _seen_signatures:
                tags.append("first_seen:true")
                _seen_signatures.add(signature)
                _record_signature_history(signature, tags)
            else:
                tags.append("first_seen:false")

    return list(set(tags))
