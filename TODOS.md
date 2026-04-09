# TODOS

## REPL

### Custom backend template syntax

**What:** Define a `--backend custom:"mycommand {prompt}"` template syntax for arbitrary CLI tools.
**Why:** Currently locked to claude/codex presets. Users with ollama, llm, or other CLI tools can't use the REPL.
**Priority:** P2
**Added:** 2026-04-08 via /plan-eng-review
**Context:** The BACKENDS dict has two entries. A custom template needs a placeholder syntax (e.g., `{prompt}`) and the first/cont distinction may not apply to all tools. About 20 lines of code to implement.
**Depends on:** Nothing, fully independent.

### Investigate streaming for claude -p

**What:** Research whether `claude -p` supports `--stream` or if stdout can be read incrementally via subprocess pipes.
**Why:** REPL blocks until full response returns. A spinner helps but real streaming would match interactive UX expectations.
**Priority:** P3
**Added:** 2026-04-08 via /plan-eng-review (outside voice)
**Context:** Would need subprocess pipe reading instead of capture_output. May not be possible with current claude CLI. Spinner is the stopgap.
**Depends on:** Claude CLI capabilities.

## Daemon (OS-level product)

### Release sequencing plan

**What:** Document explicit release sequence: (1) submit Chrome extension to Web Store early (1-3 day review), (2) ship daemon .dmg with native messaging host manifest registration, (3) onboarding flow links to CWS listing once live.
**Why:** Extension needs the native messaging host manifest registered by daemon installer. Daemon's extension path needs the Chrome extension installed. Without sequencing, users get a broken first experience.
**Priority:** P1
**Added:** 2026-04-09 via /plan-eng-review (outside voice — codex)
**Context:** Chrome Web Store review takes 1-3 days. Daemon can ship immediately via .dmg. Submit extension before daemon launch so it's live when users install. Daemon now uses pure Rust engine (no Python dependency), simplifying packaging. Sparkle auto-update adds another channel to coordinate.
**Depends on:** Packaging + notarization pipeline complete.

### Per-target undo state

**What:** Implement per-target undo keyed by (app bundle ID, window ID, element hash). Store original text + cursor position in a ring buffer (last 10 entries, auto-expire after 5 minutes). Cmd+Shift+Z restores most recent target only.
**Why:** Global undo buffer will restore wrong text across apps (e.g., undo in Terminal restores text from VS Code).
**Priority:** P2
**Added:** 2026-04-09 via /plan-eng-review (outside voice — codex)
**Context:** Current plan has global undo buffer. Real-world undo needs per-target state, cursor/selection restore, and conflict handling with app-native undo stacks. ~50 LOC with ring buffer.
**Depends on:** Core accessibility pipeline.

### Crash loop detection with safe mode

**What:** Add crash loop detection: if daemon crashes 3 times within 60 seconds, enter "safe mode" (daemon runs but Python disabled, shows troubleshooting UI with diagnostic info).
**Why:** launchd restart can enter crash loops if Python init consistently fails (corrupted install, missing dependency). Causes battery drain and system log spam.
**Priority:** P2
**Added:** 2026-04-09 via /plan-eng-review (outside voice — codex)
**Context:** launchd has built-in ThrottleInterval (default 10s between restarts). Combine with a crash counter file. After 3 rapid failures, skip Python init and show troubleshooting UI instead.
**Depends on:** launchd configuration.
