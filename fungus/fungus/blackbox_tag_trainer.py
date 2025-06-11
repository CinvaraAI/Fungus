import os
import json
import yaml
import importlib
from pathlib import Path
from collections import Counter, defaultdict

from fungus.blackbox_config import LOG_PATHS
from fungus.blackbox_tag_engine import _generate_signature  # ✅ fixed import


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


# === Tag Trainer ===
TAG_REPORT_PATH = os.path.join(LOG_PATHS["internal"], "tag_report.json")
TAG_YAML_PATH = os.path.join(LOG_PATHS["internal"], "tag_templates.yaml")
TAG_HISTORY_PATH = os.path.join(LOG_PATHS["internal"], "tag_history.jsonl")


def scan_logs_for_tags(limit_per_file=1000):
    tag_counter = Counter()
    missing_tags = defaultdict(list)
    candidate_suggestions = defaultdict(Counter)
    seen_signatures = set()

    print("[TagTrainer] Scanning logs...")

    for fname in os.listdir(LOG_PATHS["internal"]):
        if not fname.endswith(".jsonl"):
            continue

        try:
            with open(os.path.join(LOG_PATHS["internal"], fname), "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= limit_per_file:
                        break

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    tags = entry.get("tags", [])
                    payload = entry.get("payload", {})
                    ctx = {k: v for k, v in entry.items() if isinstance(v, (str, int, float))}

                    if not tags:
                        tag_type = entry.get("tag") or entry.get("step") or "untagged"
                        missing_tags[tag_type].append(entry.get("task_id", "unknown"))
                    else:
                        tag_counter.update(tags)

                    if isinstance(payload, dict):
                        for k, v in payload.items():
                            if isinstance(v, (str, int)) and f"{k}:{v}" not in tags:
                                candidate_suggestions[k].update([str(v)])

                        if "__func__" in payload:
                            try:
                                sig = _generate_signature(payload["__func__"])
                                seen_signatures.add(sig)
                            except Exception:
                                continue
        except (OSError, IOError) as e:
            print(f"[TagTrainer] Failed to read {fname}: {e}")

    return tag_counter, missing_tags, candidate_suggestions, seen_signatures


def load_tag_history():
    seen = set()
    if os.path.exists(TAG_HISTORY_PATH):
        with open(TAG_HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    sig = entry.get("signature")
                    if sig:
                        seen.add(sig)
                except json.JSONDecodeError:
                    continue
    return seen


def write_tag_report(tag_counter, missing_tags, suggestions, signatures_used):
    report = {
        "top_tags": tag_counter.most_common(50),
        "missing_tag_groups": {k: v[:10] for k, v in missing_tags.items()},
        "summary": {
            "total_tagged_events": sum(tag_counter.values()),
            "missing_tag_types": len(missing_tags),
            "known_function_signatures": len(signatures_used),
        }
    }

    with open(TAG_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[TagTrainer] Tag report written to {TAG_REPORT_PATH}")

    yaml_lines = ["# Suggested tag rules (based on common recurring fields in logs)\n"]
    if suggestions:
        for key, values in suggestions.items():
            yaml_lines.append(f"{key}:")
            for val, count in values.most_common(5):
                yaml_lines.append(f"  - {val}  # Seen {count} times")
    else:
        yaml_lines.append("# (No suggestions available)")

    with open(TAG_YAML_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))

    print(f"[TagTrainer] Tag template suggestions written to {TAG_YAML_PATH}")


def train_tags():
    tag_counts, missing, suggestions, signatures_used = scan_logs_for_tags()
    all_historical_sigs = load_tag_history()
    write_tag_report(tag_counts, missing, suggestions, all_historical_sigs.union(signatures_used))


if __name__ == "__main__":
    train_tags()
