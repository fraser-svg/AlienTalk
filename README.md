# Alchemist — Semantic Prompt Compiler

A standalone Python tool that compresses natural language prompts into token-dense **Machine Dialect**, saving 15–48% of input tokens without semantic loss.

```
python alchemist.py --prompt "I want you to take this text and turn it into a JSON object with keys for name and age"
```
```
Σ TEXT⇒{} name and age

──────────────────────────────────────────────────
⚗  COMPRESSION REPORT
──────────────────────────────────────────────────
  Original tokens:   20
  Compressed tokens: 5
  Tokens saved:      15
  Savings:           75.0%
──────────────────────────────────────────────────
```

## Why

Every token costs money and latency. System prompts, instruction sets, and constraint-heavy prompts are full of grammatical fluff that LLMs don't need for semantic grounding. Alchemist strips it algorithmically — no API calls, no overhead, deterministic output.

## How It Works

Three-stage pipeline:

```
User prompt
    │
    ▼
Stage 1: Symbolic Mapping     "summarize" → Σ, "format as a table" → ⇒table
    │                          "you are an expert" → @expert, "do not include" → !omit
    ▼                          35+ pattern→symbol mappings, longest-match-first
Stage 2: Stop-Word Stripping   Remove grammatical filler (articles, aux verbs)
    │                          80+ protected words (negation, temporal, logic) never stripped
    ▼
Stage 3: Structural Minify    Minify inline JSON, collapse lists, normalize whitespace
    │
    ▼
Compressed prompt
```

### Safety Guards (v2)

| Guard | What It Prevents |
|:---|:---|
| **Protected Words** | "not", "before", "if", "must" etc. never stripped |
| **Negation-Aware Matching** | "Do not act as a proxy" won't become `@role: proxy` |
| **Code Block Detection** | Fenced, inline, and colon-prefixed code untouched |
| **Lossless Symbol Escaping** | User's literal `Σ` won't collide with compiled `Σ` |
| **Logic Density Heuristic** | High-reasoning prompts auto-reduce compression intensity |

## Alchemist Prime

`alchemist_prime.py` extends the base compiler into a bi-directional protocol:

| Module | What | Savings |
|:---|:---|:---|
| **Echo Dialect** | 6-token directive asks LLM to respond in compressed symbols | 0–60% output (varies) |
| **Code Minifier** | AST-aware Python stripping (docstrings, comments, blanks) | 72.5% on code blocks |
| **Snippet Cache** | Deduplicates repeated code blocks across turns via `[REF:BLK_001]` | Eliminates repeats |
| **State Squeeze** | Sentence-level constraint dedup across conversation history | 35% history savings |

```
python alchemist_prime.py --prompt "You are an expert. Think step by step. Return only the code. Strict adherence to PEP 8."
```
```
@expert. CoT. ⇒code!.!strict to PEP 8.
[Reply:terse,symbols(Σ=summary ⇒{}=json CoT=reasoning !v=constraint @=role),no filler]
```

## Installation

```bash
git clone https://github.com/fraser-svg/AlienTalk.git
cd AlienTalk
```

Python 3.9+, stdlib only. No dependencies required.

Optional: `pip install tiktoken` for accurate BPE token counting (falls back to whitespace split).

## Usage

### CLI

```bash
# Compile a prompt
python alchemist.py --prompt "Your prompt here"

# From file
python alchemist.py --file prompt.txt

# JSON output
python alchemist.py --prompt "..." --json

# Decompile
python alchemist.py --prompt "Σ data ⇒table" --decompile

# Prime (bi-directional)
python alchemist_prime.py --prompt "..."

# Expand an echo response
python alchemist_prime.py --expand "CoT: step 1 → step 2. ∴ done."
```

### Python API

```python
from alchemist import PromptCompiler

compiler = PromptCompiler()

# Compile
compressed = compiler.compile("You are an expert. Summarize this report.")
# → "@expert. Σ report."

# Token savings
stats = compiler.estimate_savings("Your long prompt here...")
print(f"Saved {stats['percentage_saved']}%")

# Decompile (lossy — reverses symbols only)
readable = compiler.decompile(compressed)
```

```python
from alchemist_prime import AlchemistPrime

prime = AlchemistPrime(echo=True)

# Full pipeline: minify code + dedup snippets + compress + inject echo
compiled = prime.compile("Act as a senior dev. Think step by step...")

# Expand LLM echo response
readable = prime.expand_response("CoT: issue ← null ref. !fix add guard.")

# Multi-turn history compression
compressed_history = prime.compress_history(messages)
```

## Benchmarks

### Input Compression (Measured)

| Prompt Type | Savings | Semantic Fidelity |
|:---|:---|:---|
| System prompts | 34–48% | 100% |
| Coding instructions | 30–40% | 100% |
| Short questions | 10–20% | 100% |
| Code-heavy (protected) | 0–7% | 100% |

### vs Caveman

| | Alchemist | [Caveman](https://github.com/JuliusBrussee/caveman) |
|:---|:---|:---|
| **Compresses** | INPUT (your prompt) | OUTPUT (LLM response) |
| **Method** | Algorithmic (regex pipeline) | Prompt engineering |
| **Overhead** | 0 tokens | ~350 tokens/request |
| **Deterministic** | Yes | No |
| **API required** | No | Yes |
| **Dependencies** | Python stdlib | Node.js + LLM API |

They're complementary. Alchemist compresses what you send, Caveman compresses what comes back. Stack both for maximum savings.

### Live API Results (Claude Sonnet)

Tested with real Claude API calls — no simulation:

| Prompt | Input Saved | Echo Output Saved | Total Pipe |
|:---|:---|:---|:---|
| Code review | 7.0% | **59.9%** | **55.3%** |
| Multi-constraint code | 23.0% | 36.4% | 35.7% |
| Closures explanation | — | 27.4% | 26.3% |
| Negation-heavy | 21.1% | 24.4% | 24.0% |

## Tests

```bash
# Base compiler tests (2 scenarios)
python test_alchemist.py

# Semantic collapse stress test (32 tests)
python tests/stress_test.py

# Prime evaluation (8 criteria tests)
python tests/test_prime.py

# Thorough suite (125 deterministic tests)
python tests/test_prime_thorough.py

# Live API tests (requires key)
ANTHROPIC_API_KEY=sk-... python tests/test_prime_thorough.py --live

# Competitive benchmark vs Caveman
python tests/competitive_benchmark.py
```

## Symbol Reference

| Symbol | Meaning |
|:---|:---|
| `Σ` | Summarize |
| `Σ++` | Detailed explanation |
| `CoT` | Chain of thought / step by step |
| `⇒{}` | Convert to JSON |
| `⇒table` | Format as table |
| `⇒[]` | Format as list |
| `⇒code!` | Return only code |
| `!omit` | Do not include |
| `!strict` | Strict adherence |
| `!never` | Under no circumstances |
| `!ensure` | Make sure to / important that |
| `@expert` | You are an expert |
| `@role:` | Act as a... |
| `⟺` | Compare and contrast |
| `∴` | Therefore / in conclusion |
| `↻` | Rewrite / refactor |
| `ƒ` | Write a function |

## License

MIT
