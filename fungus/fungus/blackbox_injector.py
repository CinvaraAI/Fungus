import os
import sys
import yaml
import inspect
import importlib
import importlib.util
from types import ModuleType
from pathlib import Path

from fungus.blackbox_infect import is_excluded, blackbox_wrap, is_already_wrapped
from fungus.blackbox_config import BLACKBOX_SETTINGS


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


PROJECT_ROOT = os.getcwd()


def find_python_modules(base_dir):
    modules = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("_") and file != "__init__.py":
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                module_name = rel_path.replace(os.path.sep, ".").rsplit(".py", 1)[0]
                if "fungus" not in module_name and not module_name.startswith("."):
                    modules.append((module_name, abs_path))
    return modules


def import_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[Blackbox] Failed to import {name}: {e}")
        return None


def wrap_module_functions(module):
    if getattr(module, "__blackbox_injected__", False):
        print(f"[🛑] Skipping {module.__name__}: already injected.")
        return
    setattr(module, "__blackbox_injected__", True)

    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and not is_excluded(obj) and not is_already_wrapped(obj) and not name.startswith("_"):
            try:
                wrapped = blackbox_wrap(name)(obj)
                setattr(module, name, wrapped)
                print(f"[✔] Wrapped function: {module.__name__}.{name}")
            except Exception as e:
                print(f"[❌] Failed to wrap function {module.__name__}.{name}: {e}")
        elif inspect.isclass(obj):
            wrap_class_methods(module, obj)


def wrap_class_methods(module, cls):
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not is_excluded(method) and not is_already_wrapped(method) and not name.startswith("_"):
            try:
                wrapped = blackbox_wrap(name)(method)
                setattr(cls, name, wrapped)
                print(f"[✔] Wrapped method: {module.__name__}.{cls.__name__}.{name}")
            except Exception as e:
                print(f"[❌] Failed to wrap method {cls.__name__}.{name}: {e}")


def auto_inject():
    if not BLACKBOX_SETTINGS.get("write_logs", True):
        return

    print("[Blackbox] Auto-injection starting...")
    modules = find_python_modules(PROJECT_ROOT)
    for mod_name, mod_path in modules:
        module = import_module_from_path(mod_name, mod_path)
        if isinstance(module, ModuleType):
            wrap_module_functions(module)
    print("[Blackbox] Auto-injection complete.")


if __name__ == "__main__":
    auto_inject()
