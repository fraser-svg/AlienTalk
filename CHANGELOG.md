# Changelog

All notable changes to AlienTalk will be documented in this file.

## [0.2.0.0] - 2026-04-09

### Added
- **macOS daemon** — Tauri v2 menu bar app for system-wide prompt compression. Bounded compression queue, context-aware mode detection (full/moderate/light/blocked by app), cumulative stats tracking, user config persistence at `~/.alientalk/`. 24 Rust unit tests.
- **Chrome extension** — MV3 extension with "Optimize" button for claude.ai, chatgpt.com, gemini.google.com. ProseMirror-safe write-back, focus tracking, SPA navigation handling, native messaging bridge to daemon.
- **Monorepo structure** — Python engine moved to `engine/`, daemon at `daemon/`, extension at `extension/`.
- **PyO3 bridge** with 200ms timeout, degraded mode fallback, 64KB input size limit. Bridge is scaffolding (returns passthrough), ready for `tauri-plugin-python` wiring.
- **Context detection** — Maps macOS app bundle IDs to compression intensity. Blocks password managers and banking apps. Code editors get light compression, terminals moderate.
- **System tray** with persistent handle, stable menu item IDs, degraded mode indicator.
- **Config validation** on IPC boundary (hotkey format, bundle ID plausibility).

### Changed
- README updated for monorepo paths and speed/performance framing.
- CLAUDE.md updated with project structure and build commands.

## [0.1.0.0] - 2026-04-08

### Added
- **Terminal REPL** for subscription CLI users (Claude MAX, Codex). Transparent prompt compression in an interactive chat loop. Supports `--backend claude` (default) and `--backend codex`, with `--prime` for heavier compression.
- Stats normalization layer bridging PromptCompiler and AlchemistPrime APIs.
- "Thinking..." spinner indicator during backend execution.
- One-time tiktoken availability warning when using word-count fallback.
- 120-second subprocess timeout for backend calls.
- Shell injection prevention via list-mode subprocess (no `shell=True`).
- Graceful error handling for missing binaries, timeouts, and OS errors.
- Compiler error recovery (bad compression input doesn't crash the REPL).
- Cross-platform readline guard (Windows compatibility).
- Session summary showing total token savings on exit.
- 21 unit tests covering pure functions, error paths, and injection safety.
- CLI Pipe (`pipe.sh`) documented in README for one-shot compression.
- TODOS.md with P2 custom backend template and P3 streaming investigation.

### Changed
- README rewritten for API developer audience. Dual-benefit framing: API users save money, subscription users get faster responses and extended caps.
