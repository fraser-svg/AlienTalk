# 👽 Alchemist

**Makes your AI prompts shorter so they cost less and run faster.**

When you talk to AI models like Claude or GPT, you pay for every word you send. Most of those words are filler — "I want you to", "please make sure", "it is important that" — stuff the AI doesn't actually need to understand you. Alchemist strips all that out and replaces common instructions with short symbols, cutting your prompt size by 15–48%.

The AI still understands you perfectly. You just pay for fewer words.

```
python alchemist.py --prompt "I want you to take this text and turn it into a JSON object with keys for name and age"
```
```
Σ TEXT⇒{} name and age    (75% saved — 20 tokens → 5)
```

## Before and After

**Simple instruction — 75% smaller:**

> I want you to take this text and turn it into a JSON object with keys for name and age

```
Σ TEXT⇒{} name and age
```

**Big system prompt — 49% smaller:**

> You are an expert data analyst. I want you to summarize the following quarterly report and provide a detailed explanation of the trends. Format as a table with columns for metric, Q1 value, Q2 value, and percent change. Make sure to compare and contrast performance across regions. It is important that you think step by step about the underlying causes. Do not include any speculative projections. Please ensure that all numbers are sourced from the data provided. Keep it concise but do not sacrifice accuracy. Under no circumstances should you fabricate statistics.

```
@expert data analyst. Σ following quarterly report and Σ++ trends. ⇒table columns for
metric, Q1 value, Q2 value, and percent change.!ensure ⟺ performance across regions.
!ensure you CoT about underlying causes.!omit any speculative projections.!ensure all
numbers sourced from data provided.!brief but not sacrifice accuracy.!never should you
fabricate statistics.
```

**Coding task — 37% smaller:**

> Act as a senior Python developer. I need you to implement a thread-safe LRU cache with the following constraints: use only the \_\_new\_\_ method for singleton pattern, do not use metaclasses, the cache must handle concurrent access from multiple threads, generate a list of test cases covering edge cases, and return only the code with type annotations. Strict adherence to PEP 8. Think step by step about the data structure choice.

```
@role: senior Python developer. impl: thread-safe LRU cache following constraints: use
only __new__ method for singleton pattern, not use metaclasses, cache must handle
concurrent access from multiple threads, ⇒[] test cases covering edge cases, and ⇒code!
type annotations.!strict to PEP 8. CoT about data structure choice.
```

**Security review — 34% smaller:**

> I would like you to review the following REST API design for security and performance issues. Think step by step about each endpoint. Make sure to check for SQL injection, XSS, CSRF, and rate limiting gaps. Do not deviate from OWASP Top 10 guidelines. Format as a table with columns for endpoint, risk level, issue description, and recommended fix.

```
review following REST API design for security and performance issues. CoT about endpoint.
!ensure check for SQL injection, XSS, CSRF, and rate limiting gaps.!strict from OWASP
Top 10 guidelines. ⇒table columns for endpoint, risk level, issue description, and
recommended fix.
```

## How It Works

Alchemist runs your prompt through three steps:

1. **Symbol Swap** — Common phrases get replaced with short symbols. "Summarize" becomes `Σ`. "Format as a table" becomes `⇒table`. "You are an expert" becomes `@expert`. There are 35+ of these.

2. **Filler Removal** — Words like "the", "a", "an", "is", "are", "been", "very" get stripped. These are grammar words that AI models don't need. Important words like "not", "before", "if", "must" are always kept.

3. **Structure Cleanup** — JSON gets minified, numbered lists get compacted, extra whitespace gets removed.

The AI still gets the same instructions. It just gets them in fewer words.

## What Doesn't Get Touched

Alchemist is careful about what it compresses. These are never changed:

- **Code blocks** — Python, JavaScript, SQL, regex, anything in backticks
- **Negation** — "not", "never", "don't", "cannot" always stay (removing these would flip the meaning)
- **Logic words** — "if", "but", "unless", "before", "after", "then", "only"
- **Technical terms** — everything specific to your domain stays exact

If a prompt has lots of complex logic (if/then/else, multiple negations), Alchemist automatically dials back the compression to play it safe.

## Alchemist Prime

`alchemist_prime.py` is the advanced version. On top of everything above, it adds:

- **Code Minifier** — Strips comments, docstrings, and blank lines from Python code blocks. 72.5% savings on code while keeping the code valid.
- **Snippet Cache** — If you send the same code block twice in a conversation, the second one gets replaced with a tiny reference token instead.
- **History Compression** — If you've told the AI "follow PEP 8" three times across multiple messages, it keeps only the latest one and deletes the duplicates.
- **Echo Mode** — Adds a tiny 6-token instruction asking the AI to respond using the same short symbols. Sometimes saves 24–60% on the response too.

## Install

```bash
git clone https://github.com/fraser-svg/AlienTalk.git
cd AlienTalk
```

That's it. Python 3.9+ and nothing else. No packages to install.

Optionally run `pip install tiktoken` for more accurate token counting, but it works fine without it.

## Usage

Compress a prompt:

```bash
python alchemist.py --prompt "You are an expert. Summarize this report and format as a table."
```

Compress from a file:

```bash
python alchemist.py --file prompt.txt
```

Reverse it back to English (not perfect, but readable):

```bash
python alchemist.py --prompt "Σ data ⇒table" --decompile
```

Use Prime for code-heavy stuff:

```bash
python alchemist_prime.py --prompt "Act as a senior dev. Think step by step. Return only the code."
```

## Use It in Your Code

```python
from alchemist import PromptCompiler

compiler = PromptCompiler()
compressed = compiler.compile("You are an expert. Summarize this report.")
stats = compiler.estimate_savings("Your long prompt here...")
print(f"Saved {stats['percentage_saved']}%")
```

## Make It Always-On

Three ways to have every prompt automatically compressed.

**Python SDK Wrapper** — Swap one import line and every API call gets compressed automatically.

```python
from integrations.sdk_wrapper import AlchemistClient

client = AlchemistClient(verbose=True)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Your verbose prompt here..."}],
)
# Prompt was auto-compressed before sending.
print(client.last_stats)  # {'percentage_saved': 59.3, ...}
```

**API Proxy** — A local server that compresses prompts on the fly. Works with any programming language or tool. Just change one URL.

```bash
# Start the proxy
python integrations/proxy.py --verbose

# Tell your app to use it instead of the real API
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080

# Done. Every API call now goes through Alchemist first.
```

**Shell Alias** — For quick terminal use.

```bash
# Add this line to your ~/.zshrc or ~/.bashrc
export ALCHEMIST_HOME="/path/to/AlienTalk"
alias alc='python3 $ALCHEMIST_HOME/alchemist.py --prompt'

# Now just type:
alc "You are an expert. Summarize this report. Format as a table."
# → @expert. Σ this report. ⇒table.
```

## Real-World Results

Tested against Claude's API with real prompts. No fake numbers.

| Prompt Type | Tokens Saved |
|:---|:---|
| System prompts | 34–48% |
| Coding instructions | 30–40% |
| Short questions | 10–20% |
| Code blocks | 0–7% (protected on purpose) |
| Python code minification | 72.5% |

Live API test results (actual Claude Sonnet calls):

| Prompt | Input Saved | Output Saved | Total |
|:---|:---|:---|:---|
| Code review | 7.0% | **59.9%** | **55.3%** |
| Multi-constraint code | 23.0% | 36.4% | 35.7% |
| Closures explanation | — | 27.4% | 26.3% |
| Negation-heavy | 21.1% | 24.4% | 24.0% |

## Symbol Cheat Sheet

| Symbol | What It Means | Symbol | What It Means |
|:---|:---|:---|:---|
| `Σ` | Summarize | `!omit` | Don't include |
| `Σ++` | Explain in detail | `!strict` | Follow rules exactly |
| `CoT` | Think step by step | `!never` | Under no circumstances |
| `⇒{}` | Give me JSON | `!ensure` | Make sure to |
| `⇒table` | Give me a table | `@expert` | You're an expert |
| `⇒[]` | Give me a list | `@role:` | Act as... |
| `⇒code!` | Just the code | `⟺` | Compare these |
| `∴` | In conclusion | `↻` | Rewrite this |

## Run the Tests

```bash
python test_alchemist.py                                        # Basic tests
python tests/stress_test.py                                     # 32 edge case tests
python tests/test_prime.py                                      # Prime feature tests
python tests/test_prime_thorough.py                             # 125 thorough tests
ANTHROPIC_API_KEY=sk-... python tests/test_prime_thorough.py --live  # Real API tests
```

## License

MIT
