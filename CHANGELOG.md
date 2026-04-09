# Changelog

All notable changes to Sharp will be documented in this file.

## [0.4.0.0] - 2026-04-09

### Added
- **Two-stage pipeline** — `sharpen()` (Stage 1, human-readable) + `compress()` (Stage 2, machine-facing) + `process()` (both combined). Replaces monolithic `compile()`.
- **Cargo workspace** — `engine/` (pure Rust, `sharp-engine`) and `desktop/` (Tauri, `sharp-desktop`) as workspace members.
- **Stage 1: Sharpen** — Filler removal (hedge phrases, politeness, greetings), verbose→concise rewriting (50+ patterns), text cleanup (punctuation, capitalization, whitespace).
- **Stage 2: Compress** — Symbolic mapping (35+ patterns), stop-word stripping, JSON minification, list collapsing. Short-prompt pass-through (< 15 words).
- **Quality scorer** — 0-100 score across 4 dimensions: specificity, conciseness, structure, completeness.
- **Safety module** — Code block extraction (fenced, inline), `[keep: ...]` block protection, logic density heuristic, negation awareness, intensity scaling.
- **WASM target** — Engine compiles to WASM via `wasm-bindgen`. Exports `wasm_sharpen()`, `wasm_compress()`, `wasm_score()`.
- **Legacy compat** — `compile()` and `estimate_savings()` preserved for desktop golden parity tests.
- **JSON key order preservation** — `serde_json` `preserve_order` feature for stable minification.

### Changed
- Project renamed from AlienTalk to Sharp.
- `daemon/` renamed to `desktop/`.
- Engine extracted from inline module to standalone `sharp-engine` crate.
- Desktop depends on engine via Cargo path dependency (`pub use sharp_engine as engine`).
- Config directory: `~/.alientalk/` → `~/.sharp/`.
- Hotkey: `Cmd+Shift+Enter` → `Cmd+Shift+S`.
- Onboarding UI updated for Sharp branding and two-stage messaging.

### Removed
- Python engine (alchemist.py, alchemist_prime.py, spell.py, integrations/, tests/).
- Old inline engine module in desktop (dialect.rs, stopwords.rs, structural.rs, normalize.rs, codeblocks.rs, logic.rs).
- PLAN.md and TODOS.md (superseded by rebuild plan).

### Fixed
- Desktop bridge now calls `engine::process()` instead of `estimate_savings()`. Stage 1 (sharpen) was never firing on desktop.
- Content script `innerHTML` replaced with DOM construction (XSS hardening).
- Message listeners validate `sender.id` (cross-extension injection prevention).
- Removed unused `webRequest` permission from manifest.
- Poll dedup: content script skips re-scoring when text hasn't changed.
- MutationObserver scoped to `subtree: false` + popstate/hashchange (was firing on every streamed AI token).
- Blob URL `try/finally` guard prevents memory leak on WASM load failure.
- `compute_logic_density` no longer allocates Vec for word count.

### For contributors
- Removed stale `regex` dep from desktop Cargo.toml.
- Removed duplicate `serde_json` dev-dep from engine Cargo.toml.

### Tests
- 71 engine tests (stage1, stage2, safety, scorer, integration).
- 32 desktop unit tests.
- 2 golden parity tests (36/37 byte-identical, JSON key order now preserved).
- 105 total tests passing.

## [0.3.0.0] - 2026-04-09

### Added
- Pure Rust compression engine — 4-stage pipeline ported from Python. 39 unit tests + 2 golden parity tests.
- Diff view — before/after diff panel for first 50 compressions.
- Onboarding wizard — 3-step first-launch flow.
- Golden parity tests — 37 fixtures from Python engine.

## [0.2.1.0] - 2026-04-09

### Added
- Spell correction, text normalization, hotkey, undo support, MCP server.

## [0.2.0.0] - 2026-04-09

### Added
- macOS daemon, Chrome extension, monorepo structure.

## [0.1.0.0] - 2026-04-08

### Added
- Terminal REPL, CLI pipe, initial Python engine.
