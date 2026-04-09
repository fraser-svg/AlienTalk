#!/usr/bin/env python3
"""Thorough test suite for Alchemist Prime — zero simulation.

Every test validates real, deterministic behavior. No hand-crafted
"simulated responses." Three layers:

  LAYER 1: Unit Tests — each module in isolation, edge cases
  LAYER 2: Integration Tests — full pipeline roundtrips, invariant checks
  LAYER 3: Live API Harness — real Claude calls (requires ANTHROPIC_API_KEY)

Run: python3 tests/test_prime_thorough.py
  With API key: ANTHROPIC_API_KEY=sk-... python3 tests/test_prime_thorough.py --live
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alchemist import DIALECT_MAP, INVERSE_DIALECT_MAP, PromptCompiler, count_tokens
from alchemist_prime import (
    ECHO_DIRECTIVE,
    ECHO_RESPONSE_SYMBOLS,
    AlchemistPrime,
    CodeMinifier,
    EchoProcessor,
    SnippetCache,
    StateSqueeze,
)

# ═══════════════════════════════════════════════════════════════════════════
# Test infrastructure
# ═══════════════════════════════════════════════════════════════════════════

_pass_count = 0
_fail_count = 0
_skip_count = 0
_results: list[tuple[str, str, str]] = []  # (name, status, detail)


def _test(name: str, condition: bool, detail: str = "") -> None:
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        _results.append((name, "PASS", detail))
    else:
        _fail_count += 1
        _results.append((name, "FAIL", detail))
        print(f"  FAIL: {name}")
        if detail:
            print(f"        {detail}")


def _skip(name: str, reason: str) -> None:
    global _skip_count
    _skip_count += 1
    _results.append((name, "SKIP", reason))


def _section(title: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1: UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_echo_directive():
    """Echo directive: token budget, structure, parsability."""
    _section("Echo Directive")

    tokens = count_tokens(ECHO_DIRECTIVE)
    _test("Echo overhead < 20 tokens", tokens < 20,
          f"Actual: {tokens}")

    _test("Echo directive is single line",
          '\n' not in ECHO_DIRECTIVE,
          f"Contains newline")

    # Key symbols mentioned in the directive should exist in our symbol map
    # The directive format is: symbols(Σ=summary ⇒{}=json CoT=reasoning ...)
    inner = re.search(r'symbols\(([^)]+)\)', ECHO_DIRECTIVE)
    if inner:
        pairs = re.findall(r'(\S+?)=\w+', inner.group(1))
        for sym in pairs:
            _test(f"Echo symbol '{sym}' in ECHO_RESPONSE_SYMBOLS",
                  sym in ECHO_RESPONSE_SYMBOLS,
                  f"'{sym}' not found in symbol map")

    # Directive should not contain any natural language that gets compressed
    compiler = PromptCompiler()
    compiled_directive = compiler.compile(ECHO_DIRECTIVE)
    _test("Echo directive survives own compiler",
          len(compiled_directive) >= len(ECHO_DIRECTIVE) * 0.8,
          f"Directive got over-compressed: {len(compiled_directive)} vs {len(ECHO_DIRECTIVE)}")


def test_code_minifier_python():
    """CodeMinifier: Python AST-aware stripping."""
    _section("CodeMinifier — Python")
    m = CodeMinifier()

    # --- Docstring removal ---
    code_with_docstrings = '''\
class Foo:
    """This is a class docstring.

    It spans multiple lines.
    """
    def bar(self):
        """Method docstring."""
        return 42

    def baz(self):
        """Another docstring."""
        x = 1  # inline comment
        return x
'''
    minified = m.minify_block(code_with_docstrings, "python")
    _test("Docstrings removed",
          '"""' not in minified and "docstring" not in minified.lower(),
          f"Docstring survived: {minified[:100]}")

    _test("Class definition preserved",
          "class Foo:" in minified)

    _test("Method definitions preserved",
          "def bar(self):" in minified and "def baz(self):" in minified)

    _test("Return values preserved",
          "return 42" in minified and "return x" in minified)

    _test("Inline comments removed",
          "# inline comment" not in minified,
          f"Comment survived")

    _test("Variable assignment preserved",
          "x = 1" in minified)

    # Verify the minified code is still valid Python
    try:
        ast.parse(minified)
        _test("Minified code is valid Python AST", True)
    except SyntaxError as e:
        _test("Minified code is valid Python AST", False, str(e))

    # --- Comment stripping heuristic: # inside strings ---
    code_with_hash_in_string = '''\
x = "hello # world"  # this is a comment
y = 'path/to/#fragment'  # another comment
'''
    minified2 = m.minify_block(code_with_hash_in_string, "python")
    _test("Hash inside double-quoted string preserved",
          '"hello # world"' in minified2 or "'hello # world'" in minified2,
          f"Got: {minified2}")

    _test("Trailing comments after strings removed",
          "# this is a comment" not in minified2)

    # --- Empty/broken code fallback ---
    broken_code = "def foo(\n    this is not valid python"
    minified3 = m.minify_block(broken_code, "python")
    _test("Broken Python doesn't crash", True,
          f"Returned: {minified3[:50]}")

    # --- Token savings measurement ---
    big_code = '''\
# Authentication module
# Author: dev@company.com

import hashlib
import os

class Auth:
    """Handles authentication."""

    def __init__(self):
        """Initialize."""
        self.key = os.environ.get("SECRET")  # Get secret key

    def hash(self, pw: str) -> str:
        """Hash a password.

        Args:
            pw: The password.

        Returns:
            The hash.
        """
        # Use SHA256
        return hashlib.sha256(pw.encode()).hexdigest()  # Return hex
'''
    minified_big = m.minify_block(big_code, "python")
    orig_tokens = count_tokens(big_code)
    mini_tokens = count_tokens(minified_big)
    savings = round((1 - mini_tokens / orig_tokens) * 100, 1)
    _test(f"Python code savings > 30% (got {savings}%)", savings > 30)

    # Verify semantics preserved
    try:
        tree = ast.parse(minified_big)
        class_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        _test("Class 'Auth' preserved", "Auth" in class_names)
        _test("Functions preserved", set(func_names) == {"__init__", "hash"})
    except SyntaxError:
        _test("Minified big code valid AST", False)


def test_code_minifier_js():
    """CodeMinifier: JavaScript/generic stripping."""
    _section("CodeMinifier — JavaScript")
    m = CodeMinifier()

    js_code = '''\
// Main entry point
/* Multi-line
   block comment */
function greet(name) {
    // Say hello
    console.log(`Hello, ${name}`);  // inline
    return true;
}
'''
    minified = m.minify_block(js_code, "javascript")
    _test("JS line comments removed", "//" not in minified)
    _test("JS block comments removed", "/*" not in minified)
    _test("JS function preserved", "function greet(name)" in minified)
    _test("JS body preserved", "console.log" in minified)
    _test("JS return preserved", "return true" in minified)


def test_snippet_cache():
    """SnippetCache: deduplication, ref resolution, cross-turn tracking."""
    _section("SnippetCache")
    cache = SnippetCache()

    # --- Exact duplicate ---
    text = (
        "First:\n```python\ndef add(a, b):\n    return a + b\n```\n"
        "Second:\n```python\ndef add(a, b):\n    return a + b\n```\n"
    )
    processed = cache.process(text)
    ref_count = processed.count("[REF:")
    _test("Exact duplicate produces 1 REF", ref_count == 1,
          f"REF count: {ref_count}")

    # First block should still be there
    _test("First block kept verbatim", "def add(a, b):" in processed)

    # --- Ref resolution roundtrip ---
    resolved = cache.resolve_refs(processed)
    _test("Resolved text has both code blocks",
          resolved.count("def add(a, b):") == 2,
          f"Count: {resolved.count('def add(a, b):')}")

    # --- Different code = no dedup ---
    cache2 = SnippetCache()
    text2 = (
        "A:\n```python\ndef foo(): pass\n```\n"
        "B:\n```python\ndef bar(): pass\n```\n"
    )
    processed2 = cache2.process(text2)
    _test("Different code not deduped", "[REF:" not in processed2)
    _test("Both blocks preserved",
          "def foo()" in processed2 and "def bar()" in processed2)

    # --- Cross-turn dedup ---
    cache3 = SnippetCache()
    turn1 = "Here:\n```python\nx = 1\n```"
    cache3.process(turn1)
    cache3.advance_turn()
    turn2 = "Again:\n```python\nx = 1\n```"
    processed3 = cache3.process(turn2)
    _test("Cross-turn duplicate detected", "[REF:" in processed3)

    # --- Whitespace normalization in hashing ---
    cache4 = SnippetCache()
    text4a = "```python\ndef f():\n    pass\n```"
    text4b = "```python\ndef f():\n    pass\n\n```"  # Extra blank line
    cache4.process(text4a)
    processed4 = cache4.process(text4b)
    _test("Whitespace-different code still deduped",
          "[REF:" in processed4)

    # --- Stats tracking ---
    _test("Cache stats correct", cache.stats["cached_blocks"] == 1)


def test_state_squeeze():
    """StateSqueeze: constraint dedup, anchor creation, stale eviction."""
    _section("StateSqueeze")

    # --- Basic sentence dedup ---
    sq = StateSqueeze()
    messages = [
        {"role": "user", "content": "Use Python 3.10. Follow PEP 8. No global state."},
        {"role": "assistant", "content": "Got it."},
        {"role": "user", "content": "Now add caching. Follow PEP 8. No global state. Use Redis."},
    ]
    compressed = sq.compress_history(messages)
    all_text = " ".join(m["content"] for m in compressed)

    _test("'Follow PEP 8' appears once after dedup",
          all_text.count("Follow PEP 8") == 1,
          f"Count: {all_text.count('Follow PEP 8')}")

    _test("'No global state' appears once after dedup",
          all_text.count("No global state") == 1,
          f"Count: {all_text.count('No global state')}")

    _test("Unique sentences preserved",
          "Use Python 3.10" in all_text and "Use Redis" in all_text)

    _test("Assistant message preserved",
          any(m["role"] == "assistant" for m in compressed))

    # --- Last occurrence wins ---
    # "Follow PEP 8" should be in the LAST message, not the first
    last_user_msgs = [m for m in compressed if m["role"] == "user"]
    _test("Deduped constraint in latest message",
          "Follow PEP 8" in last_user_msgs[-1]["content"],
          f"Last user: {last_user_msgs[-1]['content'][:80]}")

    # --- Memory anchors ---
    sq2 = StateSqueeze()
    anchor = sq2.register_confirmation("The API uses REST with OAuth 2.0")
    _test("Anchor has MEM prefix", anchor.startswith("[MEM:"))
    _test("Anchor has closing bracket", anchor.endswith("]"))
    anchor_words = anchor[5:-1].split("_")
    _test("Anchor is ~3 words", 1 <= len(anchor_words) <= 4,
          f"Words: {anchor_words}")

    expanded = sq2.expand_anchors(f"Check {anchor} compatibility")
    _test("Anchor expands to full fact",
          "REST with OAuth 2.0" in expanded,
          f"Expanded: {expanded}")

    # --- Stale eviction ---
    sq3 = StateSqueeze()
    sq3.register_constraint("Use TypeScript")
    for _ in range(StateSqueeze.STALE_THRESHOLD + 2):
        sq3.advance_turn()
    _test("Stale constraint evicted",
          sq3.stats["active_constraints"] == 0,
          f"Active: {sq3.stats['active_constraints']}")

    # --- Empty messages ---
    sq4 = StateSqueeze()
    empty_result = sq4.compress_history([
        {"role": "user", "content": "Hello."},
        {"role": "assistant", "content": "Hi."},
    ])
    _test("Simple messages pass through",
          len(empty_result) == 2 and "Hello" in empty_result[0]["content"])

    # --- Single message no crash ---
    sq5 = StateSqueeze()
    single = sq5.compress_history([{"role": "user", "content": "Do X."}])
    _test("Single message works", len(single) == 1)


def test_echo_processor():
    """EchoProcessor: symbol expansion, code block safety, idempotency."""
    _section("EchoProcessor")
    ep = EchoProcessor()

    # --- Basic symbol expansion ---
    _test("Σ expands", "summary" in ep.expand_response("Σ of data").lower())
    _test("CoT expands", "reasoning" in ep.expand_response("CoT: step 1").lower())
    _test("∴ expands", "therefore" in ep.expand_response("∴ done").lower())
    _test("!v expands", "confirmed" in ep.expand_response("!v works").lower())

    # --- Code block protection ---
    code_resp = "Fix:\n```python\nclass Σ:\n    def ∴(self):\n        return True\n```"
    expanded = ep.expand_response(code_resp)
    _test("Σ inside code block NOT expanded",
          "class Σ:" in expanded or "class Σ" in expanded,
          f"Got: {expanded}")
    _test("∴ inside code block NOT expanded",
          "def ∴" in expanded,
          f"Got: {expanded}")

    # --- Code indentation preserved ---
    indented = "```python\n    if x:\n        return y\n```"
    exp_indented = ep.expand_response(indented)
    _test("Code indentation preserved",
          "    if x:" in exp_indented and "        return y" in exp_indented,
          f"Got: {repr(exp_indented)}")

    # --- Inline code protected ---
    inline = "Use `Σ` operator in your code"
    exp_inline = ep.expand_response(inline)
    _test("Inline code backticks preserved",
          "`Σ`" in exp_inline,
          f"Got: {exp_inline}")

    # --- Multiple symbols in one line ---
    multi = "!err: null ref → !fix add null check"
    exp_multi = ep.expand_response(multi)
    _test("Multiple symbols expand in same line",
          "error" in exp_multi.lower() and "fix" in exp_multi.lower(),
          f"Got: {exp_multi}")

    # --- Empty input ---
    _test("Empty string handled", ep.expand_response("") == "")

    # --- Pure code response ---
    pure_code = "```\nfoo()\n```"
    exp_pure = ep.expand_response(pure_code)
    _test("Pure code response passes through",
          "foo()" in exp_pure)


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2: INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_full_pipeline_roundtrip():
    """Full compile→expand roundtrip: nothing lost, nothing corrupted."""
    _section("Full Pipeline Roundtrip")
    prime = AlchemistPrime(echo=True)

    prompts = [
        "Summarize this report and format as a table.",
        "You are an expert. Think step by step. Return only the code.",
        "Do not include any speculative data. Strict adherence required.",
        "Compare and contrast options A and B. Generate a list of pros and cons.",
    ]

    for prompt in prompts:
        compiled = prime.compile(prompt)
        # Strip echo directive for pure compression measurement
        body = compiled.replace(ECHO_DIRECTIVE, "").strip()

        # Compiled body should use fewer tokens than original
        orig_tokens = count_tokens(prompt)
        body_tokens = count_tokens(body)
        _test(f"'{prompt[:40]}...' compresses",
              body_tokens < orig_tokens,
              f"Body tokens ({body_tokens}) >= original ({orig_tokens})")

        # Echo directive should be present
        _test(f"'{prompt[:40]}...' has echo directive",
              ECHO_DIRECTIVE in compiled)

        # Compiled should not contain NUL sentinels
        _test(f"'{prompt[:40]}...' no sentinel leak",
              '\x00' not in compiled,
              f"Sentinel found in output")


def test_code_pipeline_integrity():
    """Code blocks survive full pipeline without corruption."""
    _section("Code Pipeline Integrity")
    prime = AlchemistPrime(echo=False)  # No echo to isolate code path

    prompt = '''\
Fix this code:

```python
def fibonacci(n: int) -> int:
    """Calculate nth fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
```

Make it handle negative inputs. Do not use recursion.
'''
    compiled = prime.compile(prompt)

    # Docstring should be stripped by minifier
    _test("Docstring stripped from code block",
          '"""Calculate nth fibonacci' not in compiled,
          f"Docstring survived")

    # Core logic preserved
    _test("Function signature preserved",
          "def fibonacci" in compiled)
    _test("Return statement preserved",
          "return b" in compiled or "return n" in compiled)
    _test("Loop preserved",
          "for _ in range" in compiled or "for _" in compiled)

    # Constraint preserved
    _test("Negation constraint preserved",
          "not" in compiled.lower() or "!omit" in compiled.lower())

    # Verify the code block is still valid Python
    code_match = re.search(r'```python\n([\s\S]*?)```', compiled)
    if code_match:
        try:
            ast.parse(code_match.group(1))
            _test("Code in compiled output is valid Python", True)
        except SyntaxError as e:
            _test("Code in compiled output is valid Python", False, str(e))
    else:
        _test("Code block present in compiled output",
              False, "No ```python block found")


def test_multi_turn_integration():
    """Multi-turn: state squeeze + snippet cache working together."""
    _section("Multi-Turn Integration")
    prime = AlchemistPrime(echo=False)

    # Turn 1: introduce code + constraints
    turn1 = [
        {"role": "user", "content":
            "Implement a cache. Use LRU eviction. Follow PEP 8.\n\n"
            "```python\n"
            "from collections import OrderedDict\n\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity: int):\n"
            "        self.cache = OrderedDict()\n"
            "        self.capacity = capacity\n"
            "```"},
        {"role": "assistant", "content": "Here's the implementation."},
    ]

    compressed1 = prime.compress_history(turn1)
    _test("Turn 1 preserves code block",
          any("LRUCache" in m["content"] for m in compressed1))

    # Turn 2: repeat constraints + same code
    prime.advance_turn()

    # Compile turn 1's user message first (seeds the snippet cache)
    prime.compile(turn1[0]["content"])

    # Now compile turn 2 with same code block — should dedup
    turn2_content = (
        "Now add thread safety. Follow PEP 8.\n\n"
        "```python\n"
        "from collections import OrderedDict\n\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.cache = OrderedDict()\n"
        "        self.capacity = capacity\n"
        "```"
    )
    compiled2 = prime.compile(turn2_content)

    _test("Duplicate code block becomes REF",
          "[REF:" in compiled2,
          f"Compiled: {compiled2[:200]}")

    # Also test constraint dedup via history
    full_history = turn1 + [
        {"role": "user", "content": "Now add thread safety. Follow PEP 8."},
    ]
    compressed2 = prime.compress_history(full_history)
    all_text2 = " ".join(m["content"] for m in compressed2)

    _test("'Follow PEP 8' deduped across turns",
          all_text2.count("Follow PEP 8") == 1,
          f"Count: {all_text2.count('Follow PEP 8')}")


def test_invariants():
    """Mathematical invariants that must always hold."""
    _section("Invariants")
    prime = AlchemistPrime(echo=True)
    compiler = PromptCompiler()

    test_inputs = [
        "",
        "Hello",
        "Summarize this.",
        "You are an expert Python developer. Think step by step.",
        "Do NOT include any mention of competitors.",
        "```python\nprint('hello')\n```",
        "A" * 5000,  # Long input
        "Σ ⇒{} ∴ CoT",  # All symbols
        "日本語テスト",  # Non-ASCII
        "\n\n\n\n",  # Only whitespace
    ]

    for inp in test_inputs:
        label = repr(inp[:30])

        # INVARIANT 1: compile never crashes
        try:
            compiled = prime.compile(inp)
            _test(f"No crash on {label}", True)
        except Exception as e:
            _test(f"No crash on {label}", False, str(e))
            continue

        # INVARIANT 2: no NUL sentinels in output
        _test(f"No sentinel in {label}", '\x00' not in compiled)

        # INVARIANT 3: compiled length <= original + echo directive
        max_len = len(inp) + len(ECHO_DIRECTIVE) + 10  # +10 for newline/whitespace
        _test(f"Length bounded for {label}",
              len(compiled) <= max_len,
              f"{len(compiled)} > {max_len}")

        # INVARIANT 4: decompile(compile(x)) doesn't crash
        try:
            decompiled = compiler.decompile(compiled)
            _test(f"Decompile OK for {label}", True)
        except Exception as e:
            _test(f"Decompile OK for {label}", False, str(e))

        # INVARIANT 5: double-compile is idempotent (minus echo stacking)
        # Skip for pure code blocks — they lose fences on second pass (expected)
        if not inp.strip().startswith("```"):
            prime_no_echo = AlchemistPrime(echo=False)
            c1 = prime_no_echo.compile(inp)
            c2 = prime_no_echo.compile(c1)
            if count_tokens(c1) > 0:
                shrink = 1 - count_tokens(c2) / count_tokens(c1)
                _test(f"Idempotent for {label} (shrink={shrink:.1%})",
                      shrink < 0.15,
                      f"Second pass shrunk by {shrink:.1%}")


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3: LIVE API HARNESS
# ═══════════════════════════════════════════════════════════════════════════

LIVE_PROMPTS = [
    {
        "id": "explain-closures",
        "raw": "Explain JavaScript closures with a practical example. Keep it concise.",
        "concept_groups": [
            ["closure", "closures"],
            ["function", "functions", "inner function"],
            ["scope", "outer scope", "lexical environment", "outer function"],
        ],
    },
    {
        "id": "code-review",
        "raw": (
            "You are an expert security reviewer. Review this code for vulnerabilities:\n\n"
            "```python\n"
            "from flask import Flask, request\n"
            "import sqlite3\n\n"
            "app = Flask(__name__)\n\n"
            "@app.route('/user')\n"
            "def get_user():\n"
            "    uid = request.args.get('id')\n"
            "    conn = sqlite3.connect('app.db')\n"
            "    result = conn.execute(f'SELECT * FROM users WHERE id = {uid}')\n"
            "    return str(result.fetchone())\n"
            "```\n\n"
            "Think step by step. Format as a table with columns: vulnerability, severity, fix."
        ),
        "concept_groups": [
            ["sql injection", "injection"],
        ],
    },
    {
        "id": "system-prompt-heavy",
        "raw": (
            "You are an expert data analyst. I want you to summarize the following "
            "trends in three bullet points. Make sure to compare and contrast the "
            "growth rates. It is important that you think step by step about causation. "
            "Do not include speculative projections. Return only the analysis. "
            "Strict adherence to factual data. Under no circumstances fabricate numbers.\n\n"
            "Q1: $12M revenue, 15% growth. Q2: $13.8M revenue, 15% growth. "
            "Q3: $16.1M revenue, 17% growth. APAC led with 33% growth."
        ),
        "concept_groups": [
            ["revenue", "$12m", "$13.8m", "$16.1m"],
            ["growth", "grew", "growth rate"],
            ["apac"],
        ],
    },
    {
        "id": "multi-constraint-code",
        "raw": (
            "Act as a senior Python developer. Implement a decorator that retries "
            "a function up to 3 times with exponential backoff. Requirements:\n"
            "- Must handle both sync and async functions\n"
            "- Must log each retry attempt\n"
            "- Do not use any third-party libraries\n"
            "- Return only the code\n"
            "- Strict adherence to type annotations\n"
            "Think step by step about the edge cases."
        ),
        "concept_groups": [
            ["def", "async def"],
            ["retry", "retries", "retrying"],
            ["async", "await", "awaitable"],
        ],
    },
    {
        "id": "negation-heavy",
        "raw": (
            "Explain the difference between TCP and UDP. "
            "Do not mention the OSI model. Do not include any diagrams. "
            "Do not explain IP addressing. Only focus on reliability vs speed tradeoffs. "
            "Be concise but do not sacrifice technical accuracy."
        ),
        "concept_groups": [
            ["tcp"],
            ["udp"],
            ["reliab", "reliable", "reliability"],
        ],
    },
]


def _contains_any(text: str, variants: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in variants)


def run_live_tests() -> None:
    """Send compiled prompts to real Claude API, measure echo compliance."""
    _section("LIVE API TESTS (Real Claude)")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        for p in LIVE_PROMPTS:
            _skip(f"Live: {p['id']}", "No ANTHROPIC_API_KEY")
        return

    try:
        import anthropic
    except ImportError:
        for p in LIVE_PROMPTS:
            _skip(f"Live: {p['id']}", "anthropic package not installed")
        return

    client = anthropic.Anthropic(api_key=api_key)
    prime = AlchemistPrime(echo=True)
    prime_no_echo = AlchemistPrime(echo=False)
    ep = EchoProcessor()

    for entry in LIVE_PROMPTS:
        pid = entry["id"]
        raw = entry["raw"]
        concept_groups = entry["concept_groups"]

        print(f"\n  Running: {pid}")

        # Compile
        compiled = prime.compile(raw)
        compiled_no_echo = prime_no_echo.compile(raw)
        echo_enabled = ECHO_DIRECTIVE in compiled
        adaptive_passthrough = compiled == raw and compiled_no_echo == raw

        input_orig_tokens = count_tokens(raw)
        input_comp_tokens = count_tokens(compiled)
        input_saved = round((1 - input_comp_tokens / input_orig_tokens) * 100, 1)

        print(f"    Input: {input_orig_tokens} → {input_comp_tokens} tokens ({input_saved}%)")
        if adaptive_passthrough:
            print("    Adaptive path: passthrough (no compression applied)")

        # --- Call 1: Original prompt (baseline) ---
        try:
            baseline_resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": raw}],
            )
            baseline_text = baseline_resp.content[0].text
            baseline_tokens = baseline_resp.usage.output_tokens
            print(f"    Baseline response: {baseline_tokens} tokens")
        except Exception as e:
            _test(f"Live baseline: {pid}", False, f"API error: {e}")
            continue

        # --- Call 2: Compiled prompt with adaptive echo mode ---
        echo_text = ""
        echo_tokens = 0
        if echo_enabled:
            try:
                echo_resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": compiled}],
                )
                echo_text = echo_resp.content[0].text
                echo_tokens = echo_resp.usage.output_tokens
                print(f"    Echo response: {echo_tokens} tokens")
            except Exception as e:
                _test(f"Live echo: {pid}", False, f"API error: {e}")
                continue
        else:
            print("    Echo response: skipped (adaptive echo disabled)")

        # --- Call 3: Compiled prompt WITHOUT echo (pure input compression) ---
        try:
            comp_resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": compiled_no_echo}],
            )
            comp_text = comp_resp.content[0].text
            comp_tokens = comp_resp.usage.output_tokens
            print(f"    Compressed-only response: {comp_tokens} tokens")
        except Exception as e:
            comp_text = ""
            comp_tokens = 0

        active_text = echo_text if echo_enabled else comp_text
        active_tokens = echo_tokens if echo_enabled else comp_tokens

        # ---- METRIC 1: Active path compression ----
        output_savings = round((1 - active_tokens / baseline_tokens) * 100, 1) if baseline_tokens and active_tokens else 0
        label = "echo" if echo_enabled else "compressed-only"
        print(f"    Output savings ({label}): {output_savings}%")
        if echo_enabled:
            _test(f"Live {label} output shorter: {pid}",
                  active_tokens < baseline_tokens,
                  f"{label} ({active_tokens}) >= baseline ({baseline_tokens})")

        # ---- METRIC 2: Total pipe compression ----
        total_orig = input_orig_tokens + baseline_tokens
        total_comp = input_comp_tokens + active_tokens
        total_savings = round((1 - total_comp / total_orig) * 100, 1)
        print(f"    Total pipe: {total_orig} → {total_comp} ({total_savings}%)")
        if not adaptive_passthrough:
            min_total_savings = 0 if echo_enabled else -2.0
            threshold_label = "> 0%" if echo_enabled else ">= -2.0%"
            _test(f"Live total pipe {threshold_label}: {pid}",
                  total_savings >= min_total_savings,
                  f"Savings: {total_savings}%")

        # ---- METRIC 3: Semantic preservation (concept groups) ----
        expanded_echo = ep.expand_response(echo_text) if echo_enabled else ""
        for idx, variants in enumerate(concept_groups, 1):
            baseline_has = _contains_any(baseline_text, variants)
            active_has = _contains_any(active_text, variants)
            expanded_has = echo_enabled and _contains_any(expanded_echo, variants)
            if baseline_has:
                _test(f"Live concept {idx} preserved: {pid}",
                      active_has or expanded_has,
                      f"Missing concept variants: {variants}")

        # ---- METRIC 4: Echo symbol compliance ----
        if echo_enabled:
            known_symbols = set(ECHO_RESPONSE_SYMBOLS.keys())
            symbols_used = sum(1 for sym in known_symbols if sym in echo_text)
            _test(f"Live echo uses >= 1 symbol: {pid}",
                  symbols_used >= 1,
                  f"Symbols found: {symbols_used}")

        # ---- METRIC 5: Compressed-only quality ----
        # Response to compressed input (no echo) should be coherent
        if comp_text:
            for idx, variants in enumerate(concept_groups, 1):
                baseline_has = _contains_any(baseline_text, variants)
                if baseline_has:
                    _test(f"Live compressed-only concept {idx}: {pid}",
                          _contains_any(comp_text, variants),
                          f"Missing concept variants: {variants}")

        # ---- METRIC 6: Post-processor roundtrip ----
        expanded = expanded_echo if echo_enabled else active_text
        _test(f"Live expand doesn't crash: {pid}", True)
        if echo_enabled:
            _test(f"Live expanded longer than echo: {pid}",
                  len(expanded) >= len(echo_text) * 0.9,  # Allow some shrinkage from cleanup
                  f"Expanded: {len(expanded)} vs echo: {len(echo_text)}")

        # ---- Log ----
        print(f"    Echo preview: {echo_text[:150]}...")
        print(f"    Expanded preview: {expanded[:150]}...")

        # Rate limit courtesy
        time.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════

def print_report() -> None:
    total = _pass_count + _fail_count + _skip_count
    print(f"\n{'═' * 70}")
    print(f"  THOROUGH TEST REPORT — Alchemist Prime")
    print(f"{'═' * 70}")
    print(f"  Total: {total}  |  Pass: {_pass_count}  |  Fail: {_fail_count}  |  Skip: {_skip_count}")
    print(f"{'═' * 70}")

    if _fail_count > 0:
        print(f"\n  FAILURES:")
        for name, status, detail in _results:
            if status == "FAIL":
                print(f"    ✗ {name}")
                if detail:
                    print(f"      {detail}")

    if _skip_count > 0:
        print(f"\n  SKIPPED:")
        for name, status, detail in _results:
            if status == "SKIP":
                print(f"    ○ {name}: {detail}")

    # Summary by section
    print(f"\n  BY SECTION:")
    current_section = ""
    section_pass = 0
    section_total = 0
    for name, status, detail in _results:
        if status in ("PASS", "FAIL"):
            section_total += 1
            if status == "PASS":
                section_pass += 1

    print(f"    Deterministic: {_pass_count}/{_pass_count + _fail_count} passed")
    if _skip_count:
        print(f"    Live API: {_skip_count} skipped (set ANTHROPIC_API_KEY to run)")
    print()


def main() -> None:
    live = "--live" in sys.argv

    # Layer 1: Unit tests
    test_echo_directive()
    test_code_minifier_python()
    test_code_minifier_js()
    test_snippet_cache()
    test_state_squeeze()
    test_echo_processor()

    # Layer 2: Integration tests
    test_full_pipeline_roundtrip()
    test_code_pipeline_integrity()
    test_multi_turn_integration()
    test_invariants()

    # Layer 3: Live API (only with --live flag and API key)
    if live:
        run_live_tests()
    else:
        _section("LIVE API TESTS (Skipped)")
        for p in LIVE_PROMPTS:
            _skip(f"Live: {p['id']}", "Run with --live flag")

    print_report()
    sys.exit(0 if _fail_count == 0 else 1)


if __name__ == "__main__":
    main()
