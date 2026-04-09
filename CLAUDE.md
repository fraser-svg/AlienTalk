# Sharp

Two-stage prompt optimization for AI. Rust engine + macOS desktop + Chrome extension.

## Project structure

- `engine/` — Pure Rust engine crate (`sharp-engine`): sharpen() + compress() pipeline, 71 tests
- `desktop/` — Rust/Tauri v2 macOS menu bar daemon (`sharp-desktop`), depends on engine crate
- `extension/` — Chrome MV3 extension (WASM engine, self-contained, 6 site adapters, Stage 2 request interception)

## Build & test

```bash
# Full workspace (105 tests)
cargo test

# Engine only (71 tests)
cargo test -p sharp-engine

# Desktop only (34 tests: 32 unit + 2 golden parity)
cargo test -p sharp-desktop

# Extension: load unpacked from extension/ in chrome://extensions
# Hotkey: Cmd+Shift+S (macOS)
```

## Architecture

Two-stage pipeline:
- **Stage 1 (Sharpen)**: Human-readable improvement — filler removal, verbose→concise rewriting, cleanup. User sees and approves this.
- **Stage 2 (Compress)**: Machine-facing compression — symbolic mapping, stop-word stripping, JSON minification. Invisible to user, applied to outbound API requests.

Public API:
- `sharpen(text)` — Stage 1 only
- `compress(text)` — Stage 2 only (skips prompts < 15 words)
- `process(text)` — Both stages combined
- `compile(text)` — Legacy compat (cleanup + compress, no short-prompt guard)

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
