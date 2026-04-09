# Sharp

**Two-stage prompt optimization for AI.**

Sharp makes your prompts better in two ways:
1. **Sharpen** (Stage 1) — Removes filler, rewrites verbose phrases, fixes structure. You see the result and approve it.
2. **Compress** (Stage 2) — Replaces patterns with symbols, strips articles, minifies JSON. Invisible to you — applied automatically to outbound API requests.

```
Input:  "Hey, I was wondering if you could help me out. In order to fix this bug,
         I need you to take into consideration the error log and make changes to
         the authentication module. Please make sure to be concise. Thank you!"

Stage 1 (you see):  "Fix this bug. Consider the error log and change the authentication module. Be concise."
Stage 2 (AI sees):  "Fix bug. Consider error log, change auth module. !brief"

73 tokens → 14 tokens (81% saved)
```

## Architecture

- `engine/` — Pure Rust crate. No platform dependencies. Compiles to native and WASM.
- `desktop/` — macOS Tauri v2 menu bar daemon. Tray icon, onboarding wizard, system-wide hotkey.
- `extension/` — Chrome MV3 extension. Self-contained with WASM engine. 6 site adapters, Stage 2 request interception.

## Build & Test

```bash
# Full workspace (105 tests)
cargo test

# Engine only (71 tests)
cargo test -p sharp-engine

# Desktop only (34 tests including golden parity)
cargo test -p sharp-desktop
```

Requires Rust 1.85+.

## Engine API

```rust
use sharp_engine::{sharpen, compress, process};

// Stage 1 only — human-readable improvement
let result = sharpen("In order to fix this, take into consideration the logs");
// result.sharpened_text = "To fix this, consider the logs"

// Stage 2 only — machine compression (skips prompts < 15 words)
let result = compress("Explain step by step how databases work and summarize the findings");
// result.compressed_text = "CoT databases work Σ findings"

// Both stages
let result = process("your verbose prompt here...");
// result.sharpened_text — what the user sees
// result.compressed_text — what the AI receives
// result.score_before / score_after — quality scores (0-100)
// result.total_saved — tokens saved
```

## What Gets Protected

- Code blocks (fenced and inline)
- Negation ("not", "never", "don't")
- Logic operators ("if", "unless", "before", "then")
- `[keep: ...]` blocks (user-marked content)
- Domain-specific terms

High logic-density prompts automatically get lighter compression.

## License

MIT
