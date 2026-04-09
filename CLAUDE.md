# AlienTalk

Semantic prompt compression for AI. Python library + macOS daemon + Chrome extension.

## Project structure

- `engine/` — Python compression engine (PromptCompiler, AlchemistPrime, integrations)
- `daemon/` — Rust/Tauri v2 macOS menu bar daemon (pure Rust engine, 67 tests)
- `extension/` — Chrome MV3 extension (native messaging, ProseMirror write-back)

## Build & test

```bash
# Python engine (run from engine/ directory)
cd engine && python test_alchemist.py
python -m pytest tests/test_spell.py -v

# Rust daemon
cd daemon && cargo test

# MCP server
python -m engine.integrations.mcp_server

# Extension: load unpacked from extension/ in chrome://extensions
# Hotkey: Cmd+Shift+Enter (macOS) / Ctrl+Shift+Enter
```

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
