# 👽 AlienTalk

**Make every AI interaction faster. One import line. No code changes.**

AlienTalk sits between your app and the AI model. Every prompt gets automatically compressed before it reaches the API, so the model starts responding sooner and you fit more into context windows and rate limits.

```python
# Before
from anthropic import Anthropic
client = Anthropic()

# After: swap one line, faster responses
from engine.integrations.sdk_wrapper import AlienTalkClient
client = AlienTalkClient()

# Everything else stays the same. Your app doesn't change.
```

## Who This Is For

You're building something that calls Claude or GPT, a chatbot, an agent, a pipeline, a batch processor. You're sending thousands of prompts. You want faster responses and better throughput.

AlienTalk plugs into your code and compresses every prompt before it reaches the model. The AI still gets the same instructions. Responses come back faster.

AlienTalk works three ways:
- **Python library** — Drop-in SDK wrapper, API proxy, CLI pipe, batch processing
- **macOS daemon** (new) — System-wide prompt compression via menu bar app. Global hotkey compresses text in any app via Accessibility API.
- **Chrome extension** (new) — One-click "Optimize" button on claude.ai, chatgpt.com, gemini.google.com

## How It Works

Your prompts are full of words the AI doesn't need. "I want you to", "please make sure", "it is important that" — all filler. AlienTalk strips it out and replaces common patterns with short tokens.

```
Your app sends:
  "I want you to take this text and turn it into a JSON object with keys for name and age"

AlienTalk sends to the API:
  "Σ TEXT⇒{} name and age"

Tokens: 20 → 5 (75% saved)
```

It runs four steps on every prompt:

1. **Spell Correction** — SymSpell-powered O(1) typo correction. 650 tech terms protected (kubectl, pytorch, terraform). Your misspelled prompts get fixed before compression, so "analize" becomes "analyze" not garbage.
2. **Pattern Replacement** — 35+ common instruction phrases get swapped for short symbols (`summarize` → `Σ`, `format as a table` → `⇒table`, `you are an expert` → `@expert`)
3. **Filler Removal** — Grammar words the AI doesn't need ("the", "a", "is", "been") get stripped. Important words like "not", "if", "before", "must" are never touched.
4. **Structure Cleanup** — Embedded JSON gets minified, lists get compacted, whitespace gets trimmed, punctuation normalized.

The AI still understands and responds correctly. Tested against Claude's API with real calls.

## Install

```bash
git clone https://github.com/fraser-svg/AlienTalk.git
cd AlienTalk
```

Python 3.9+. No dependencies for core compression. Optional extras:
- `pip install tiktoken` for more accurate token counting
- `pip install symspellpy` for spell correction (recommended)

## Integration

### Python SDK Wrapper (Easiest)

Swap your import. Everything else stays the same.

```python
from engine.integrations.sdk_wrapper import AlienTalkClient

client = AlienTalkClient(verbose=True)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Your normal prompt here..."}],
)

# [alientalk] 27→11 tokens (59.3% saved)   ← printed to stderr
# Response is identical to what you'd get without AlienTalk.
```

### API Proxy (Any Language)

Don't use Python? Run the proxy. It sits between your app and Anthropic's API. Change one URL. Works with JavaScript, Go, Rust, curl, anything.

```bash
# Terminal 1: start the proxy
python engine/integrations/proxy.py --verbose

# Terminal 2: tell your app to use it
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080

# That's it. Every API call now goes through AlienTalk.
```

### Terminal REPL (Subscription Users)

Use AlienTalk with Claude MAX, Codex, or any CLI, no API key needed.

```bash
# Start a compressed chat session (uses claude by default)
python engine/integrations/repl.py

# Use with Codex
python engine/integrations/repl.py --backend codex

# Heavier compression with AlchemistPrime
python engine/integrations/repl.py --prime
```

You type normally. Every message is compressed before it reaches the LLM. Responses come back unmodified. Conversation continuity uses `--continue`, which resumes the last Claude session (parallel Claude sessions may interfere).

### CLI Pipe (One-shot)

Compress a single prompt and pipe it to any CLI tool.

```bash
echo "Your verbose prompt" | ./engine/integrations/pipe.sh | claude
```

### MCP Server (IDE Integration)

Use AlienTalk directly from Claude Code, Cursor, or any MCP-compatible IDE.

```bash
# Start the MCP server
python -m engine.integrations.mcp_server
```

Exposes two tools: `compile()` for prompt compression and `estimate_savings()` for checking how much a prompt would shrink. Add to your IDE's MCP config and compress prompts without leaving your editor.

### Direct (Batch Processing)

Compress prompts in bulk before sending them yourself.

```python
from engine.alchemist import PromptCompiler

compiler = PromptCompiler()

prompts = load_your_prompts()  # thousands of prompts
compressed = [compiler.compile(p) for p in prompts]

# Send compressed prompts to the API however you want.
# Check savings:
stats = compiler.estimate_savings(prompts[0])
print(f"Saved {stats['percentage_saved']}%")
```

## macOS Daemon (Preview)

A Tauri v2 menu bar app that compresses prompts system-wide. Runs as a background daemon with a system tray icon.

**What it does:** Global hotkey (Cmd+Shift+Enter) reads text from any focused input, compresses it through the Python engine, and writes it back. Context-aware: lighter compression in code editors, full compression in chat interfaces, blocks password managers and banking apps.

**Status:** Architecture complete, pipeline tested (24 Rust unit tests). Python bridge is scaffolding, needs `tauri-plugin-python` wiring. See `daemon/` for source.

**Prerequisites:** Rust 1.85+, Tauri CLI v2, Python 3.9+ dev headers, macOS 12+.

```bash
cd daemon && cargo build
```

## Chrome Extension (Preview)

MV3 extension that adds an "Optimize" button to claude.ai, chatgpt.com, and gemini.google.com.

**What it does:** One click (or Cmd+Shift+Enter) compresses your prompt in-place. Shows savings percentage with one-click undo. Communicates with the daemon via Chrome Native Messaging. Auto-reconnects if the daemon restarts.

**Features:** Keyboard hotkey, per-element undo, site-adapted button positioning, accessible (ARIA labels, screen reader support), exponential backoff reconnection, human-readable error messages.

**Status:** Content script with ProseMirror-safe write-back, SPA navigation handling, focus tracking. Needs daemon running for actual compression.

Load unpacked from `extension/` in `chrome://extensions`.

## What Gets Compressed

| Prompt Type | Savings |
|:---|:---|
| System prompts (instruction-heavy) | 34–48% |
| Coding instructions | 30–40% |
| Short questions | 10–20% |
| Code blocks | 0–7% (protected) |

## What Never Gets Compressed

- **Code** — anything in backticks, fences, or after `code:` patterns
- **Negation** — "not", "never", "don't" (removing these flips the meaning)
- **Logic** — "if", "but", "unless", "before", "after", "then", "only"
- **Technical terms** — domain-specific words stay exact

If a prompt has lots of complex logic, AlienTalk automatically reduces compression to play it safe.

## Real API Results

Tested with actual Claude Sonnet API calls. Not simulated.

| Prompt | Input Saved | Response Quality |
|:---|:---|:---|
| Code review | 7.0% | Identical |
| Multi-constraint code | 23.0% | Identical |
| Negation-heavy | 21.1% | Identical |
| System prompt | 32.5% | Identical |

180+ deterministic tests passing. 32 semantic safety tests passing. Zero meaning lost.

## Advanced: AlienTalk Prime

`alchemist_prime.py` adds extra compression for heavier workloads:

- **Code Minifier** — Strips comments, docstrings, blank lines from Python code in your prompts. 72.5% savings on code blocks.
- **Snippet Cache** — Same code block sent twice in a conversation? Second one becomes a tiny reference token.
- **History Compression** — Repeated constraints across messages get deduped. "Follow PEP 8" said three times becomes one.

```python
from engine.alchemist_prime import AlchemistPrime

prime = AlchemistPrime()
compressed = prime.compile("Your prompt with code blocks...")
compressed_history = prime.compress_history(conversation_messages)
```

## Tests

```bash
# Python engine (run from engine/ directory)
cd engine
python test_alchemist.py                                                # Basic tests
python -m pytest tests/test_spell.py -v                                 # 71 spell correction tests
python engine/tests/stress_test.py                                      # 32 safety tests
python engine/tests/test_prime.py                                       # Prime features
python engine/tests/test_repl.py                                        # REPL unit tests
python engine/tests/test_prime_thorough.py                              # 125 thorough tests
ANTHROPIC_API_KEY=sk-... python engine/tests/test_prime_thorough.py --live  # Real API tests

# Rust daemon
cd daemon && cargo test                                                 # 24 unit tests
```

## License

MIT
