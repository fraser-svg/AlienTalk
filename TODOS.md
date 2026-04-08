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
