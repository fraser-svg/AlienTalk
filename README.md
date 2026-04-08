# 👽 Alchemist: Token-Efficient Prompt Compiler

## Overview

Alchemist is a semantic prompt compiler that reduces input tokens by 15–48% by converting natural language prompts into a token-dense Machine Dialect. The tool strips grammatical fluff, replaces common instruction patterns with Unicode symbols, and minifies embedded data structures — all without losing meaning.

```
python alchemist.py --prompt "I want you to take this text and turn it into a JSON object with keys for name and age"
```
```
Σ TEXT⇒{} name and age    (75% saved — 20 tokens → 5)
```

## Examples

**Simple instruction — 75% saved (20 → 5 tokens):**

> I want you to take this text and turn it into a JSON object with keys for name and age

```
Σ TEXT⇒{} name and age
```

**System prompt — 49% saved (92 → 47 tokens):**

> You are an expert data analyst. I want you to summarize the following quarterly report and provide a detailed explanation of the trends. Format as a table with columns for metric, Q1 value, Q2 value, and percent change. Make sure to compare and contrast performance across regions. It is important that you think step by step about the underlying causes. Do not include any speculative projections. Please ensure that all numbers are sourced from the data provided. Keep it concise but do not sacrifice accuracy. Under no circumstances should you fabricate statistics.

```
@expert data analyst. Σ following quarterly report and Σ++ trends. ⇒table columns for
metric, Q1 value, Q2 value, and percent change.!ensure ⟺ performance across regions.
!ensure you CoT about underlying causes.!omit any speculative projections.!ensure all
numbers sourced from data provided.!brief but not sacrifice accuracy.!never should you
fabricate statistics.
```

**Coding task — 37% saved (71 → 45 tokens):**

> Act as a senior Python developer. I need you to implement a thread-safe LRU cache with the following constraints: use only the \_\_new\_\_ method for singleton pattern, do not use metaclasses, the cache must handle concurrent access from multiple threads, generate a list of test cases covering edge cases, and return only the code with type annotations. Strict adherence to PEP 8. Think step by step about the data structure choice.

```
@role: senior Python developer. impl: thread-safe LRU cache following constraints: use
only __new__ method for singleton pattern, not use metaclasses, cache must handle
concurrent access from multiple threads, ⇒[] test cases covering edge cases, and ⇒code!
type annotations.!strict to PEP 8. CoT about data structure choice.
```

**Security review — 34% saved (59 → 39 tokens):**

> I would like you to review the following REST API design for security and performance issues. Think step by step about each endpoint. Make sure to check for SQL injection, XSS, CSRF, and rate limiting gaps. Do not deviate from OWASP Top 10 guidelines. Format as a table with columns for endpoint, risk level, issue description, and recommended fix.

```
review following REST API design for security and performance issues. CoT about endpoint.
!ensure check for SQL injection, XSS, CSRF, and rate limiting gaps.!strict from OWASP
Top 10 guidelines. ⇒table columns for endpoint, risk level, issue description, and
recommended fix.
```

## Key Features

**Input Compression:** The tool delivers 15–48% token savings on prompts, with instruction-heavy system prompts hitting the top of that range. 100% semantic fidelity across all 32 stress tests.

**Three-Stage Pipeline:**
- Symbolic Mapping: 35+ patterns replaced with dense symbols (`summarize` → `Σ`, `format as a table` → `⇒table`, `you are an expert` → `@expert`)
- Stop-Word Stripping: Grammatical filler removed with 80+ protected words that are never touched (negation, temporal, logic, modals)
- Structural Minification: Inline JSON minified, lists collapsed, whitespace normalized

**Semantic Safety Guards:** Negation-aware matching prevents "do not act as a proxy" from becoming `@role: proxy`. Code blocks (fenced, inline, colon-prefixed) are detected and left untouched. Literal Unicode symbols in user text are escaped to prevent collision with compiled symbols. A logic density heuristic auto-reduces compression intensity for reasoning-heavy prompts.

**Alchemist Prime:** An extended version that adds AST-aware code minification (72.5% savings on Python code blocks), cross-turn snippet deduplication via `[REF:BLK_001]` tokens, sentence-level constraint dedup across conversation history (35% savings), and a 6-token echo directive for experimental output compression.

## Installation

```bash
git clone https://github.com/fraser-svg/AlienTalk.git
cd AlienTalk
```

Python 3.9+, stdlib only. No dependencies required.

Optional: `pip install tiktoken` for accurate BPE token counting. Falls back to whitespace split if unavailable.

## Usage

Compile a prompt:

```bash
python alchemist.py --prompt "You are an expert. Summarize this report and format as a table."
```

Compile from file:

```bash
python alchemist.py --file prompt.txt
```

Decompile back to natural language (lossy — reverses symbols only):

```bash
python alchemist.py --prompt "Σ data ⇒table" --decompile
```

Use Prime for code-heavy prompts and multi-turn compression:

```bash
python alchemist_prime.py --prompt "Act as a senior dev. Think step by step. Return only the code."
```

Expand a compressed LLM response:

```bash
python alchemist_prime.py --expand "CoT: issue ← null ref. !fix add guard. ∴ done."
```

## Python API

```python
from alchemist import PromptCompiler

compiler = PromptCompiler()
compressed = compiler.compile("You are an expert. Summarize this report.")
stats = compiler.estimate_savings("Your long prompt here...")
print(f"Saved {stats['percentage_saved']}%")
```

```python
from alchemist_prime import AlchemistPrime

prime = AlchemistPrime(echo=True)
compiled = prime.compile("Act as a senior dev. Think step by step...")
readable = prime.expand_response("CoT: step 1 → step 2. ∴ done.")
compressed_history = prime.compress_history(messages)
```

## Always-On Integration

Three ways to make Alchemist run on every prompt automatically.

**SDK Wrapper (Python):** Drop-in replacement for the Anthropic client. Every user message is compiled before it hits the API.

```python
from integrations.sdk_wrapper import AlchemistClient

client = AlchemistClient(verbose=True)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Your verbose prompt here..."}],
)
# Prompt was auto-compressed. Check stats:
print(client.last_stats)  # {'percentage_saved': 59.3, ...}
```

**API Proxy:** Sits between any client and Anthropic's API. Works with any language or tool — just change the base URL.

```bash
# Start the proxy
python integrations/proxy.py --verbose

# Point your client at it
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080

# All API calls now auto-compressed — no code changes needed
```

**CLI Pipe:** Shell alias for quick use.

```bash
# Add to ~/.zshrc or ~/.bashrc
export ALCHEMIST_HOME="/path/to/AlienTalk"
alias alc='python3 $ALCHEMIST_HOME/alchemist.py --prompt'

# Then:
alc "You are an expert. Summarize this report. Format as a table."
# → @expert. Σ this report. ⇒table.
```

## Benchmarks

**Input Compression (Measured):** System prompts see 34–48% savings, coding instructions 30–40%, short questions 10–20%. Code blocks are protected and see 0–7%. Semantic fidelity is 100% across all tested prompts.

**Code Minification (Measured):** The AST-aware Python minifier strips docstrings, comments, and blank lines for 72.5% savings on code blocks while preserving valid syntax.

**Live API Results (Claude Sonnet):** Tested with real API calls against Claude — no simulation. Best total pipe savings of 55.3% on code review tasks. Echo output compression ranged from 24–60% depending on prompt type.

| Prompt | Input Saved | Echo Output Saved | Total Pipe |
|:---|:---|:---|:---|
| Code review | 7.0% | **59.9%** | **55.3%** |
| Multi-constraint code | 23.0% | 36.4% | 35.7% |
| Closures explanation | — | 27.4% | 26.3% |
| Negation-heavy | 21.1% | 24.4% | 24.0% |

## What's Preserved

Code blocks, inline code, SQL queries, regex patterns, negation words, temporal ordering (before/after/then), conditional logic (if/unless/but), modals (must/should/can), and all technical terminology remain unchanged. Only grammatical filler and recognized instruction patterns are compressed.

## Symbol Reference

| Symbol | Meaning | Symbol | Meaning |
|:---|:---|:---|:---|
| `Σ` | Summarize | `!omit` | Do not include |
| `Σ++` | Detailed explanation | `!strict` | Strict adherence |
| `CoT` | Chain of thought | `!never` | Under no circumstances |
| `⇒{}` | Convert to JSON | `!ensure` | Make sure to |
| `⇒table` | Format as table | `@expert` | You are an expert |
| `⇒[]` | Format as list | `@role:` | Act as a... |
| `⇒code!` | Return only code | `⟺` | Compare and contrast |
| `∴` | In conclusion | `↻` | Rewrite / refactor |

## Tests

```bash
python test_alchemist.py                                        # Base scenarios
python tests/stress_test.py                                     # 32 semantic collapse tests
python tests/test_prime.py                                      # Prime evaluation criteria
python tests/test_prime_thorough.py                             # 125 deterministic tests
python tests/competitive_benchmark.py                           # Competitive benchmark
ANTHROPIC_API_KEY=sk-... python tests/test_prime_thorough.py --live  # Real API tests
```

## License

MIT
