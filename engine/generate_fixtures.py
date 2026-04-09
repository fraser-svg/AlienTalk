#!/usr/bin/env python3
"""Generate golden-file fixtures from the Python compression engine.

These fixtures become the parity test corpus for the Rust engine.
Output: daemon/tests/fixtures/golden.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add engine/ to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.alchemist import PromptCompiler

FIXTURES: list[dict[str, str]] = [
    # --- Filler removal ---
    {"name": "filler_iwantyouto", "input": "I want you to explain how databases work"},
    {"name": "filler_couldyou", "input": "Could you please summarize this article for me"},
    {"name": "filler_idlikeyou", "input": "I'd like you to rewrite the following paragraph"},

    # --- Symbolic mapping ---
    {"name": "sym_cot", "input": "Think step by step about how to solve this problem"},
    {"name": "sym_summarize", "input": "Summarize the key findings from the research paper"},
    {"name": "sym_json", "input": "Convert to JSON the following data"},
    {"name": "sym_expert", "input": "You are an expert in distributed systems"},
    {"name": "sym_role", "input": "Act as a senior software engineer"},
    {"name": "sym_function", "input": "Write a function that calculates fibonacci numbers"},
    {"name": "sym_compare", "input": "Compare and contrast Python and Rust"},
    {"name": "sym_table", "input": "Format as a table the following data"},
    {"name": "sym_strict", "input": "Do not deviate from the instructions provided"},
    {"name": "sym_brief", "input": "Be concise in your response"},
    {"name": "sym_chain", "input": "Explain step by step how neural networks learn"},

    # --- Negation-aware (should NOT map) ---
    {"name": "neg_donot_act", "input": "Do not act as a therapist in this conversation"},
    {"name": "neg_never_pretend", "input": "Never pretend you are a doctor"},
    {"name": "neg_not_expert", "input": "You are not an expert so be careful"},

    # --- Stop-word stripping ---
    {"name": "stop_basic", "input": "The analysis of the data was performed with the tools"},
    {"name": "stop_protected", "input": "If the value is not valid then return an error"},

    # --- Structural minification ---
    {"name": "struct_json", "input": '{"name": "John", "age": 30, "city": "New York"}'},
    {"name": "struct_list", "input": "1. First item\n2. Second item\n3. Third item"},
    {"name": "struct_bullets", "input": "- Alpha\n- Beta\n- Gamma"},

    # --- Code block protection ---
    {"name": "code_fenced", "input": "Fix this code:\n```python\ndef hello():\n    print('world')\n```\nMake it better"},
    {"name": "code_inline", "input": "The function `calculate_total()` is broken"},

    # --- Logic density (high-logic should reduce compression) ---
    {"name": "logic_high", "input": "If x > 0 then return true, but not if the mutex is locked. Unless the semaphore is released and the thread is safe, do not proceed."},
    {"name": "logic_low", "input": "Please summarize the article about machine learning"},

    # --- Escape handling ---
    {"name": "escape_sigma", "input": "The equation uses Σ notation for summation"},
    {"name": "escape_arrow", "input": "The map function transforms A → B"},

    # --- Combined pipeline ---
    {"name": "full_system_prompt", "input": "You are an expert in Python programming. I want you to explain step by step how to implement a binary search algorithm. Be concise. Format as a numbered list. Do not deviate from the topic."},
    {"name": "full_coding", "input": "I need you to write a function that takes a list of integers and returns the two numbers that add up to a target sum. Think step by step about the most efficient approach."},
    {"name": "full_analysis", "input": "Could you please analyze and provide a detailed explanation of the differences between REST and GraphQL APIs? Compare and contrast their performance characteristics. Format as a table."},

    # --- Edge cases ---
    {"name": "edge_empty", "input": ""},
    {"name": "edge_whitespace", "input": "   \n\n   "},
    {"name": "edge_short", "input": "Hi"},
    {"name": "edge_punctuation", "input": "Wait!!!! What???  Really....."},
    {"name": "edge_unicode", "input": "日本語のテキストを翻訳してください"},
    {"name": "edge_mixed", "input": "Translate to English: こんにちは world"},
]


def main() -> None:
    compiler = PromptCompiler()
    results = []

    for fixture in FIXTURES:
        compiled = compiler.compile(fixture["input"])
        results.append({
            "name": fixture["name"],
            "input": fixture["input"],
            "expected": compiled,
        })

    out_dir = Path(__file__).parent.parent / "daemon" / "tests" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "golden.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"Generated {len(results)} fixtures → {out_path}")


if __name__ == "__main__":
    main()
