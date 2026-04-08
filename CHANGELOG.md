# Changelog

All notable changes to AlienTalk will be documented in this file.

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
