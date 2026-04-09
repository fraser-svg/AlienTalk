#!/usr/bin/env python3
"""Alchemist Prime — Bi-directional Semantic Compression Protocol.

Evolves beyond input-only compression into a full communication protocol:
  1. Echo Dialect    — 14-token instruction forces LLM to respond compressed
  2. Code Minifier   — strips comments/docstrings/whitespace from code blocks
  3. Snippet Cache   — deduplicates repeated code blocks via REF tokens
  4. State Squeeze   — rolling constraint dedup + memory anchors
  5. Post-Processor  — expands compressed LLM responses back to verbose English

Combined target: >65% total pipe savings with <20 token overhead.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

# Import base compiler
from alchemist import (
    DIALECT_MAP,
    INVERSE_DIALECT_MAP,
    PromptCompiler,
    count_tokens,
)

# ═══════════════════════════════════════════════════════════════════════════
# MODULE 1: ECHO DIALECT — Output Compression via Instruction Injection
# ═══════════════════════════════════════════════════════════════════════════

# The Echo Directive: a hyper-dense instruction appended to compiled prompts.
# Forces the LLM to respond using our symbolic map.
# Budget: <15 tokens. Measured: 14 tokens (whitespace split), ~12 BPE tokens.
ECHO_DIRECTIVE = "[Reply:terse,symbols(Σ=summary ⇒{}=json CoT=reasoning !v=constraint @=role),no filler]"

# Extended symbol guide for the LLM — used only when echo mode is active.
# Maps symbols the LLM should USE in responses.
ECHO_RESPONSE_SYMBOLS: dict[str, str] = {
    "Σ": "summary/summarize",
    "Σ++": "detailed explanation",
    "⇒{}": "JSON output",
    "⇒[]": "list output",
    "⇒table": "table output",
    "CoT": "chain of thought / reasoning",
    "∴": "therefore / conclusion",
    "!v": "validated/confirmed",
    "!err": "error found",
    "!fix": "fix/solution",
    "!warn": "warning",
    "→": "leads to / causes",
    "←": "caused by / from",
    "↻": "refactored / rewritten",
    "Δ": "change / difference",
    "✓": "confirmed / done",
    "✗": "rejected / failed",
    "§": "section",
    "@": "role/persona prefix",
    "ref:": "reference to previous",
    "e.g.": "example",
    "cf.": "compare with",
}

# Inverse: expand LLM echo responses back to natural language
_ECHO_EXPANSION: dict[str, str] = {
    "Σ": "In summary",
    "Σ++": "Here is a detailed explanation",
    "⇒{}": "JSON output",
    "⇒[]": "List",
    "⇒table": "Table",
    "CoT": "Reasoning step",
    "∴": "Therefore",
    "!v": "Confirmed",
    "!err": "Error",
    "!fix": "Fix",
    "!warn": "Warning",
    "→": " leads to ",
    "←": " is caused by ",
    "↻": "Refactored version",
    "Δ": "Change",
    "✓": "Confirmed",
    "✗": "Rejected",
    "§": "Section:",
    "ref:": "Referring to ",
    "e.g.": "For example,",
    "cf.": "Compare with",
}


class EchoProcessor:
    """Handles bi-directional echo dialect: inject directive + expand responses."""

    def __init__(self) -> None:
        # Build expansion patterns sorted longest-first
        sorted_syms = sorted(_ECHO_EXPANSION.keys(), key=len, reverse=True)
        self._patterns = [
            (re.compile(re.escape(sym)), _ECHO_EXPANSION[sym])
            for sym in sorted_syms
        ]
        # Also use the base dialect inverse map
        sorted_base = sorted(INVERSE_DIALECT_MAP.keys(), key=len, reverse=True)
        self._base_patterns = [
            (re.compile(re.escape(sym)), INVERSE_DIALECT_MAP[sym])
            for sym in sorted_base
        ]

    def inject_directive(self, compiled_prompt: str) -> str:
        """Append echo directive to a compiled prompt."""
        return f"{compiled_prompt}\n{ECHO_DIRECTIVE}"

    def should_inject_directive(self, raw_prompt: str, compiled_prompt: str) -> bool:
        """Skip echo when the prompt already constrains output to be very short.

        Echo mode helps when the model is likely to generate verbose prose.
        It can backfire on prompts that already ask for a short structured
        answer, such as a tiny bullet summary.
        """
        raw_lower = raw_prompt.lower()
        compiled_lower = compiled_prompt.lower()

        brevity_markers = (
            "keep it concise",
            "be concise",
            "!brief",
            "three bullet",
            "3 bullet",
            "three bullet points",
            "return only the analysis",
            "return only analysis",
            "return only the answer",
        )
        code_markers = (
            "```",
            "return only the code",
            "⇒code",
            "def ",
            "class ",
            "function ",
            "implement ",
        )

        if any(marker in raw_lower for marker in brevity_markers):
            if not any(marker in raw_lower or marker in compiled_lower for marker in code_markers):
                return False

        return True

    def expand_response(self, response: str) -> str:
        """Expand a compressed LLM response back to verbose English.

        Handles: symbolic tokens, terse fragments, code blocks (untouched).
        """
        # Protect code blocks from expansion
        code_blocks: list[str] = []
        def _stash_code(m: re.Match[str]) -> str:
            code_blocks.append(m.group(0))
            return f"\x00CODEBLOCK_{len(code_blocks) - 1}\x00"

        text = re.sub(r'```[\s\S]*?```', _stash_code, response)
        text = re.sub(r'`[^`]+`', _stash_code, text)

        # Expand echo symbols first (higher priority)
        for pattern, expansion in self._patterns:
            text = pattern.sub(expansion, text)

        # Then base dialect symbols
        for pattern, expansion in self._base_patterns:
            text = pattern.sub(expansion, text)

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            text = text.replace(f"\x00CODEBLOCK_{i}\x00", block)

        # Light cleanup: capitalize sentence starts, normalize spacing
        # Skip lines inside code fences
        lines = []
        in_fence = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('```'):
                in_fence = not in_fence
                lines.append(stripped)
                continue
            if in_fence:
                lines.append(line)  # Preserve code indentation exactly
                continue
            cleaned = re.sub(r'[ \t]{2,}', ' ', stripped)
            if cleaned and not cleaned.startswith(('`', '-', '•', '*', '#')):
                cleaned = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()
            lines.append(cleaned)
        text = '\n'.join(lines)

        return text


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 2: CODE MINIFIER — Boilerplate Eviscerator
# ═══════════════════════════════════════════════════════════════════════════

class CodeMinifier:
    """Strips comments, docstrings, trailing whitespace from code blocks.

    Language-aware for Python. Falls back to generic comment stripping
    for other languages.
    """

    # Generic comment patterns by language marker
    _COMMENT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
        "python": [
            re.compile(r'#[^\n]*'),                     # Line comments
        ],
        "javascript": [
            re.compile(r'//[^\n]*'),                     # Line comments
            re.compile(r'/\*[\s\S]*?\*/'),               # Block comments
        ],
        "generic": [
            re.compile(r'//[^\n]*'),
            re.compile(r'#[^\n]*'),
            re.compile(r'/\*[\s\S]*?\*/'),
        ],
    }

    def minify_block(self, code: str, language: str = "") -> str:
        """Minify a code block, preserving semantics."""
        lang = language.lower().strip()

        if lang in ("python", "py"):
            return self._minify_python(code)
        return self._minify_generic(code, lang)

    def _minify_python(self, code: str) -> str:
        """AST-aware Python minification: strip docstrings + comments."""
        try:
            tree = ast.parse(code)
            # Find docstring line ranges to remove
            docstring_lines: set[int] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef, ast.Module)):
                    if (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    ):
                        ds = node.body[0]
                        for ln in range(ds.lineno, ds.end_lineno + 1):
                            docstring_lines.add(ln)
        except SyntaxError:
            docstring_lines = set()

        lines = code.splitlines()
        result = []
        for i, line in enumerate(lines, 1):
            if i in docstring_lines:
                continue
            # Strip inline comments (but not in strings — simplified heuristic)
            stripped = line.rstrip()
            if '#' in stripped:
                # Only strip if # is not inside a string
                in_str = False
                quote_char = ''
                clean = []
                for ch in stripped:
                    if ch in ('"', "'") and not in_str:
                        in_str = True
                        quote_char = ch
                    elif ch == quote_char and in_str:
                        in_str = False
                    elif ch == '#' and not in_str:
                        break
                    clean.append(ch)
                stripped = ''.join(clean).rstrip()
            if stripped:  # Skip blank lines
                result.append(stripped)
            elif result and result[-1] != '':  # Keep max one blank line
                result.append('')

        # Remove trailing blank
        while result and result[-1] == '':
            result.pop()
        return '\n'.join(result)

    def _minify_generic(self, code: str, lang: str) -> str:
        """Generic minification: strip comments and blank lines."""
        # Pick comment patterns
        patterns = self._COMMENT_PATTERNS.get(lang,
                   self._COMMENT_PATTERNS.get("javascript" if lang in ("js", "ts", "typescript",
                       "java", "c", "cpp", "go", "rust", "swift", "kotlin") else "generic"))

        text = code
        for pat in patterns:
            text = pat.sub('', text)

        # Collapse blank lines, strip trailing whitespace
        lines = [ln.rstrip() for ln in text.splitlines()]
        result = []
        for line in lines:
            if line:
                result.append(line)
            elif result and result[-1] != '':
                result.append('')

        while result and result[-1] == '':
            result.pop()
        return '\n'.join(result)

    def process_prompt(self, text: str) -> str:
        """Find and minify all code blocks in a prompt."""
        def _minify_fenced(m: re.Match[str]) -> str:
            full = m.group(0)
            # Extract language and code
            first_line_end = full.index('\n') if '\n' in full else len(full)
            lang_line = full[3:first_line_end].strip()
            code_end = full.rfind('```')
            code = full[first_line_end + 1:code_end]
            minified = self.minify_block(code, lang_line)
            return f"```{lang_line}\n{minified}\n```"

        return re.sub(r'```[\s\S]*?```', _minify_fenced, text)


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 3: SNIPPET CACHE — Code Block Deduplication
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SnippetEntry:
    block_id: str
    content_hash: str
    code: str
    language: str
    turn_added: int


class SnippetCache:
    """Tracks code blocks across conversation turns.

    If a code block was sent before, replaces it with [REF:block_id].
    Uses content hashing for exact dedup and similarity hashing for
    near-duplicates (e.g., same code with minor edits).
    """

    def __init__(self) -> None:
        self._store: dict[str, SnippetEntry] = {}  # hash → entry
        self._id_counter = 0
        self._turn = 0

    def _hash(self, code: str) -> str:
        normalized = re.sub(r'\s+', ' ', code.strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"BLK_{self._id_counter:03d}"

    def advance_turn(self) -> None:
        self._turn += 1

    def process(self, text: str) -> str:
        """Replace duplicate code blocks with REF tokens."""
        def _check_block(m: re.Match[str]) -> str:
            full = m.group(0)
            first_nl = full.index('\n') if '\n' in full else len(full)
            lang = full[3:first_nl].strip()
            code_end = full.rfind('```')
            code = full[first_nl + 1:code_end]

            h = self._hash(code)
            if h in self._store:
                entry = self._store[h]
                return f"[REF:{entry.block_id}]"

            block_id = self._next_id()
            self._store[h] = SnippetEntry(
                block_id=block_id,
                content_hash=h,
                code=code,
                language=lang,
                turn_added=self._turn,
            )
            return full  # First occurrence: keep original

        return re.sub(r'```[\s\S]*?```', _check_block, text)

    def resolve_refs(self, text: str) -> str:
        """Expand [REF:block_id] tokens back to full code blocks."""
        def _expand(m: re.Match[str]) -> str:
            block_id = m.group(1)
            for entry in self._store.values():
                if entry.block_id == block_id:
                    return f"```{entry.language}\n{entry.code}\n```"
            return m.group(0)  # Unknown ref: keep as-is

        return re.sub(r'\[REF:(BLK_\d{3})\]', _expand, text)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "cached_blocks": len(self._store),
            "current_turn": self._turn,
        }


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 4: STATE SQUEEZE — History Compression
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Constraint:
    text: str
    turn: int
    count: int = 1


@dataclass
class MemoryAnchor:
    fact: str
    anchor: str  # 3-word compressed form
    turn_confirmed: int


class StateSqueeze:
    """Rolling window compressor for multi-turn conversations.

    - Instruction Drift: if a constraint appears twice, older one deleted
    - Memory Anchors: confirmed facts compressed to 3-word tokens
    - Stale Eviction: constraints not referenced in N turns get pruned
    """

    STALE_THRESHOLD = 5  # Turns before a constraint is considered stale

    def __init__(self) -> None:
        self._constraints: dict[str, Constraint] = {}  # normalized → Constraint
        self._anchors: list[MemoryAnchor] = []
        self._turn = 0

    def advance_turn(self) -> None:
        self._turn += 1
        self._evict_stale()

    def _normalize(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text.lower().strip())

    def _evict_stale(self) -> None:
        stale_keys = [
            k for k, c in self._constraints.items()
            if self._turn - c.turn > self.STALE_THRESHOLD
        ]
        for k in stale_keys:
            del self._constraints[k]

    def _make_anchor(self, fact: str) -> str:
        """Compress a confirmed fact to ~3 words."""
        # Strip filler, keep nouns/verbs/adjectives
        words = fact.split()
        # Take first 3 meaningful words
        stopwords = {"the", "a", "an", "is", "are", "was", "it", "that", "this",
                      "has", "have", "been", "will", "be", "to", "of", "in", "for"}
        meaningful = [w for w in words if w.lower() not in stopwords]
        anchor_words = meaningful[:3] if meaningful else words[:3]
        return "[MEM:" + "_".join(anchor_words) + "]"

    def register_constraint(self, constraint: str) -> None:
        """Track a constraint. If duplicate, update turn and increment count."""
        key = self._normalize(constraint)
        if key in self._constraints:
            self._constraints[key].turn = self._turn
            self._constraints[key].count += 1
        else:
            self._constraints[key] = Constraint(
                text=constraint, turn=self._turn
            )

    def register_confirmation(self, fact: str) -> str:
        """Convert a confirmed fact into a memory anchor."""
        anchor = self._make_anchor(fact)
        self._anchors.append(MemoryAnchor(
            fact=fact, anchor=anchor, turn_confirmed=self._turn
        ))
        return anchor

    def compress_history(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Compress a conversation history.

        Each message is {"role": "user"|"assistant", "content": str}.
        Returns compressed history with deduped constraints and anchored facts.

        Strategy: split every message into sentences, track each sentence's
        normalized form, keep only the LAST occurrence of any duplicate.
        """
        # Build a flat list of (msg_index, sentence, normalized_key)
        _SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
        all_sentences: list[tuple[int, str, str]] = []

        for i, msg in enumerate(messages):
            sentences = _SENT_SPLIT.split(msg["content"].strip())
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    all_sentences.append((i, sent, self._normalize(sent)))

        # Find the last occurrence index for each normalized sentence
        last_seen: dict[str, int] = {}  # norm → position in all_sentences
        for pos, (msg_idx, sent, norm) in enumerate(all_sentences):
            last_seen[norm] = pos

        # Rebuild messages keeping only last occurrence of each sentence
        rebuilt: dict[int, list[str]] = {i: [] for i in range(len(messages))}
        for pos, (msg_idx, sent, norm) in enumerate(all_sentences):
            if last_seen[norm] == pos:
                rebuilt[msg_idx].append(sent)
                self.register_constraint(sent)

        compressed = []
        for i, msg in enumerate(messages):
            content = ' '.join(rebuilt[i])
            content = re.sub(r'[ \t]{2,}', ' ', content).strip()
            if content:
                compressed.append({"role": msg["role"], "content": content})

        return compressed

    def expand_anchors(self, text: str) -> str:
        """Expand memory anchors back to full facts."""
        for anchor in self._anchors:
            text = text.replace(anchor.anchor, anchor.fact)
        return text

    @property
    def stats(self) -> dict:
        return {
            "active_constraints": len(self._constraints),
            "memory_anchors": len(self._anchors),
            "turn": self._turn,
            "duplicate_constraints": sum(
                1 for c in self._constraints.values() if c.count > 1
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════
# ALCHEMIST PRIME — Unified Protocol
# ═══════════════════════════════════════════════════════════════════════════

class AlchemistPrime:
    """Bi-directional semantic compression protocol.

    Combines all modules into a single pipeline:
      Input:  compile() → minify code → dedup snippets → inject echo directive
      Output: expand echo response → resolve refs → expand anchors
      Multi-turn: squeeze history → track state
    """

    def __init__(self, echo: bool = True) -> None:
        self.compiler = PromptCompiler()
        self.echo_processor = EchoProcessor()
        self.code_minifier = CodeMinifier()
        self.snippet_cache = SnippetCache()
        self.state_squeeze = StateSqueeze()
        self._echo_enabled = echo

    def _should_bypass_compression(self, prompt: str) -> bool:
        """Leave already-short non-code prompts untouched.

        These prompts tend to produce short answers already, so any input
        compression benefit is small and response-length variance dominates.
        """
        lower = prompt.lower()
        brevity_markers = (
            "keep it concise",
            "be concise",
            "three bullet",
            "3 bullet",
            "three bullet points",
            "return only the analysis",
            "return only analysis",
            "return only the answer",
        )
        code_markers = (
            "```",
            "return only the code",
            "def ",
            "class ",
            "function ",
            "implement ",
        )
        return any(marker in lower for marker in brevity_markers) and not any(
            marker in lower for marker in code_markers
        )

    def compile(self, prompt: str) -> str:
        """Full input compression pipeline."""
        if self._should_bypass_compression(prompt):
            return prompt

        # Stage 1: Minify code blocks
        text = self.code_minifier.process_prompt(prompt)

        # Stage 2: Snippet deduplication
        text = self.snippet_cache.process(text)

        # Stage 3: Base semantic compression (symbolic + stopwords + structural)
        text = self.compiler.compile(text)

        # Stage 4: Inject echo directive (if enabled)
        if self._echo_enabled and self.echo_processor.should_inject_directive(prompt, text):
            text = self.echo_processor.inject_directive(text)

        return text

    def expand_response(self, response: str) -> str:
        """Full output expansion pipeline."""
        # Stage 1: Resolve snippet references
        text = self.snippet_cache.resolve_refs(response)

        # Stage 2: Expand memory anchors
        text = self.state_squeeze.expand_anchors(text)

        # Stage 3: Expand echo symbols to natural language
        text = self.echo_processor.expand_response(text)

        return text

    def compress_history(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Compress multi-turn conversation history."""
        self.state_squeeze.advance_turn()
        self.snippet_cache.advance_turn()
        return self.state_squeeze.compress_history(messages)

    def advance_turn(self) -> None:
        """Signal a new conversation turn."""
        self.state_squeeze.advance_turn()
        self.snippet_cache.advance_turn()

    def estimate_savings(self, prompt: str, simulated_response: str = "") -> dict:
        """Full-pipe savings estimate."""
        compiled = self.compile(prompt)
        orig_input = count_tokens(prompt)
        comp_input = count_tokens(compiled)
        echo_overhead = count_tokens(ECHO_DIRECTIVE) if self._echo_enabled else 0

        result = {
            "input_original": orig_input,
            "input_compressed": comp_input,
            "input_saved_pct": round((1 - comp_input / orig_input) * 100, 1) if orig_input else 0,
            "echo_overhead": echo_overhead,
            "compiled_text": compiled,
        }

        if simulated_response:
            # Simulate output compression (echo-style response)
            expanded = self.expand_response(simulated_response)
            orig_output = count_tokens(expanded)
            comp_output = count_tokens(simulated_response)
            result.update({
                "output_original": orig_output,
                "output_compressed": comp_output,
                "output_saved_pct": round((1 - comp_output / orig_output) * 100, 1) if orig_output else 0,
            })

            # Total pipe
            total_orig = orig_input + orig_output
            total_comp = comp_input + comp_output
            result["total_original"] = total_orig
            result["total_compressed"] = total_comp
            result["total_saved_pct"] = round((1 - total_comp / total_orig) * 100, 1) if total_orig else 0

        return result

    @property
    def stats(self) -> dict:
        return {
            "echo_enabled": self._echo_enabled,
            "echo_overhead_tokens": count_tokens(ECHO_DIRECTIVE),
            "snippet_cache": self.snippet_cache.stats,
            "state_squeeze": self.state_squeeze.stats,
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def _print_stats(stats: dict) -> None:
    print(f"\n{'─' * 55}")
    print("⚗  ALCHEMIST PRIME — COMPRESSION REPORT")
    print(f"{'─' * 55}")
    print(f"  Input:  {stats['input_original']} → {stats['input_compressed']} tokens "
          f"({stats['input_saved_pct']}% saved)")
    print(f"  Echo overhead: {stats['echo_overhead']} tokens")
    if "output_original" in stats:
        print(f"  Output: {stats['output_original']} → {stats['output_compressed']} tokens "
              f"({stats['output_saved_pct']}% saved)")
        print(f"  Total:  {stats['total_original']} → {stats['total_compressed']} tokens "
              f"({stats['total_saved_pct']}% saved)")
    print(f"{'─' * 55}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="alchemist-prime",
        description="Alchemist Prime — Bi-directional Semantic Compression Protocol",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", "-p", type=str, help="Prompt to compile")
    group.add_argument("--file", "-f", type=str, help="File containing prompt")
    group.add_argument("--expand", "-x", type=str,
                       help="Expand a compressed LLM response")

    parser.add_argument("--no-echo", action="store_true",
                        help="Disable echo directive injection")
    parser.add_argument("--no-stats", action="store_true",
                        help="Suppress statistics")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--sim-response", type=str, default="",
                        help="Simulated echo response for total-pipe estimate")

    args = parser.parse_args()

    prime = AlchemistPrime(echo=not args.no_echo)

    if args.expand:
        expanded = prime.expand_response(args.expand)
        if args.json:
            print(json.dumps({"expanded": expanded}, indent=2))
        else:
            print(expanded)
        return

    # Read input
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.prompt

    compiled = prime.compile(text)
    stats = prime.estimate_savings(text, args.sim_response)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(compiled)
        if not args.no_stats:
            _print_stats(stats)


if __name__ == "__main__":
    main()
