# Fungus
Pluggable Observability Layer for Python

Fungus is a plug-and-play runtime instrumentation layer for Python projects — a modular telemetry and logging framework designed for AI-driven workflows.

It embeds quietly into your system to provide logging, tagging, metadata capture, and lifecycle-aware behaviors — without requiring you to rewrite existing logic.

This system was created entirely through prompt engineering using GPT-4.
I have no formal software training and don’t write code myself — I guided and structured this system through iterative prompting.
It could benefit from security reviews, testing, and hardening. If you're a developer and want to help, contribute, or audit it, I’d love to collaborate.

---

## 🧠 Why it exists

I believe prompt engineering is systems design.
This repo is my way of proving that — showing what's possible when someone with no formal training collaborates with AI to build something real, modular, and extensible.

Fungus was built for environments where:
- Decorators need to be injected or auto-applied across a dynamic codebase
- Contextual tags guide agent-based dev tools like GPT or Aider
- Consistent logging and traceability are essential for debugging or orchestration
- Modularity matters because tools rewrite code, paths drift, and names shift

---

## 🚀 Features

- 🧩 Plug-and-play: Just import and configure — no rewrites
- 🎯 AOP-style decorators: Logging, tagging, context injection
- 🔁 Retention: Archives and preserves behavioral data automatically (By default, checks for 300GB+ of log storage and compresses the oldest 250GB — customize as needed)
- 📦 Alias-driven: Stable imports + paths across refactors (Note: config.yaml must live at /(project root)/dynamics/config.yaml unless you modify the loader manually)
- ⚙️ Lifecycle hooks: on_startup, on_shutdown, on_pause via YAML (Currently only auto_inject is active, but retention_check, tag_trainer, and archive_layer1 are included and ready to use)

---

## 📂 Structure

The system includes:
- `blackbox_agent.py` – Core context & logging interface
- `blackbox_config.py` – Global settings and alias paths
- `blackbox_writer.py` – Log writer + structuring
- `blackbox_retention.py` – Archiving logic
- `blackbox_tag_engine.py` – Contextual tagging
- `blackbox_tag_trainer.py` – Training + tagging adaptation
- `blackbox_infect.py` – Decorator definitions (wraps)
- `blackbox_injector.py` – Manual injection layer
- `config.yaml` – Alias paths, imports, and lifecycle config

---

📦 Usage

Fungus is meant to live alongside your application code — not be cloned directly into it.
It assumes a certain folder structure and internal module layout.

To integrate it cleanly:
- Place the entire fungus/ folder in the root of your project.
- Ensure you're running your app from the project root, so imports like from fungus.blackbox_agent import ... work properly.
- Create a dynamics/config.yaml file (or copy the sample) — this is required for config resolution.

⚠️ Important: Fungus relies on internal imports like from fungus.blackbox_config import ....
These will break if the folder is renamed, moved, or not treated as a package.

---
🔌 Plugging It In

After adding fungus to your project and configuring fungus_config.yaml, integration takes just a few lines.

Example: Startup Lifecycle

from fungus.blackbox_injector import auto_inject

if __name__ == "__main__":
    auto_inject()
    # Your application logic

# This will scan your project for functions and classes, and automatically wrap them for telemetry.

FastAPI Example:

@app.on_event("startup")
def startup():
    config, _ = _load_config()
    startup_config = config.get("background_tasks", {}).get("on_startup", {})

    for task_name in startup_config.get("non-thread", []):
        resolve_import(task_name)()

    for task_name in startup_config.get("threading", []):
        threading.Thread(target=resolve_import(task_name), daemon=True).start()

@app.on_event("shutdown")
def shutdown():
    shutdown_tasks = config.get("background_tasks", {}).get("on_shutdown", [])
    for task_name in shutdown_tasks:
        try:
            resolve_import(task_name)()
        except Exception as e:
            print(f"Failed shutdown task {task_name}: {e}")

This makes Fungus fully lifecycle-aware — your tasks, your rules, your config.

---

## 📜 License

Licensed under the Apache 2.0 License — open-source, free to use, modify, extend, and share.

---

I’m sharing this in the hope of finding:
- Developers who want to help polish, test, and extend the system
- Mentors who believe in nontraditional builders
- People interested in backing or collaborating on future stages of this project

I’ve spent over 100 hours iterating and refining this — without ever writing code manually.
I’m releasing it as proof of my ability, my work ethic, and my belief that anyone with the right tools can build real systems.

This is part of a larger vision to create a community-built platform for AI-native software development.

Want to follow or join the journey?

➡️ [https://discord.gg/dYsuAVjV](https://discord.gg/dYsuAVjV)

— CinvaraAI
