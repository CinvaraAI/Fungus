import importlib
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

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


# Dynamically resolved imports
BLACKBOX_SETTINGS = resolve_import("blackbox_settings")
write_blackbox_log = resolve_import("write_blackbox_log")
tag_for_context = resolve_import("tag_for_context")


# Context-local variable
_current_ctx = ContextVar("blackbox_context", default={})


def set_ctx(ctx):
    _current_ctx.set(ctx or {})


def get_ctx():
    return _current_ctx.get()


def record_event(log_type, ctx=None, tag=None, content=None, level="info", visibility="internal", log_id=None):
    if not BLACKBOX_SETTINGS.get("write_logs", True):
        return

    ctx = ctx or get_ctx()
    tag = tag or "event"
    timestamp = datetime.utcnow().isoformat()

    event = {
        "__ts__": timestamp,
        "subsystem": log_type,
        "tag": tag,
        "level": level,
        "user_id": ctx.get("user_id", "anon"),
        "project_id": ctx.get("project_id", "unknown"),
        "task_id": ctx.get("task_id", "unknown"),
        "session_id": ctx.get("session_id"),
        "step": ctx.get("step"),
        "log_id": log_id,
        "payload": content or {},
        # Optional tagging logic for context-aware logs
        "tags": tag_for_context(
            obj=content.get("__func__") if isinstance(content, dict) and "__func__" in content else None,
            ctx=ctx,
            result=content
        )
    }

    write_blackbox_log(log_type, event, visibility=visibility)


def record_error_event(log_type, ctx=None, tag=None, content=None, visibility="internal"):
    record_event(log_type, ctx, tag, content, level="error", visibility=visibility)


class BlackboxAgent:
    def __init__(self):
        self.session_id = self._generate_session_id()
        self.metadata_context = {}

    def _generate_session_id(self):
        return datetime.utcnow().strftime("BB-%Y%m%d-%H%M%S")

    # Optional: Use if your system tracks projects
    def generate_project_id(self, label=None):
        date_str = datetime.utcnow().strftime("%Y%m%d")
        suffix = uuid.uuid4().hex[:6]
        return f"proj-{date_str}-{suffix}"

    # Optional: Use if your system tracks tasks
    def generate_task_id(self, prefix="task"):
        timestamp = datetime.utcnow().strftime("%H%M%S")
        suffix = uuid.uuid4().hex[:5]
        return f"{prefix}-{timestamp}-{suffix}"

    # Optional: Log contextual metadata for traceability
    def log_metadata(self, task_id=None, context_link=None, extra=None):
        ts = datetime.utcnow().isoformat()
        entry = {
            "timestamp": ts,
            "session_id": self.session_id,
            "task_id": task_id,
            "context_link": context_link,
            "extra": extra or {}
        }

        if BLACKBOX_SETTINGS.get("write_logs", True):
            write_blackbox_log("contextual_link", entry)
