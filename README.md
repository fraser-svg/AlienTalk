# 👽 Alchemist: Token-Efficient Prompt Compiler

## Overview

Alchemist is a semantic prompt compiler that reduces input tokens by 15–48% by converting natural language prompts into a token-dense Machine Dialect. The tool strips grammatical fluff, replaces common instruction patterns with Unicode symbols, and minifies embedded data structures — all without losing meaning.

```
python alchemist.py --prompt "I want you to take this text and turn it into a JSON object with keys for name and age"
```
```
Σ TEXT⇒{} name and age    (75% saved — 20 tokens → 5)
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
