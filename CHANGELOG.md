# Changelog

All notable changes to AlienTalk will be documented in this file.

## [0.2.1.0] - 2026-04-09

### Added
- **Spell correction** — SymSpell-powered O(1) typo correction before compression. 650-word tech allowlist (kubectl, pytorch, terraform, etc.) prevents false corrections on technical terms. Prompt-domain word boosts ensure "analyze" beats "realize".
- **Text normalization** — Sentence-initial capitalization, repeated punctuation collapse (!!!→!), ellipsis preservation, space-before-punctuation cleanup. Runs after spell correction, before compression.
- **Hotkey** — Cmd+Shift+Enter (macOS) / Ctrl+Shift+Enter triggers prompt optimization from any supported site.
- **Undo support** — One-click undo after optimization. Per-element undo state via WeakMap, element-scoped so switching fields doesn't cross-contaminate.
- **MCP server** — `compile()` and `estimate_savings()` tools for Claude Code, Cursor, and other MCP-compatible IDEs. Zero install beyond the Python engine.
- **Reconnection logic** — Extension auto-reconnects to daemon with exponential backoff (1s to 30s max).
- **Onboarding state** — Extension popup shows "Get started" guidance when daemon is offline, stats at zero for first-time users.

### Changed
- Extension button position adapts per site (ChatGPT, Gemini, Claude) to avoid overlapping send buttons.
- Daemon error codes mapped to human-readable messages in extension.
- Added accessibility attributes (aria-label, aria-live, role="status") to all interactive extension elements.
- Double-click guard prevents duplicate compression requests.
- URL sent to daemon stripped to origin only (no pathname or query params).

### Fixed
- Ellipsis (...) no longer collapsed by repeated punctuation regex.
- Reconnection backoff no longer resets prematurely on instant daemon disconnect.
- Spell correction exception handling broadened to catch RuntimeError/OSError from SymSpell.
- Undo now targets the correct element even after switching focus.

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
