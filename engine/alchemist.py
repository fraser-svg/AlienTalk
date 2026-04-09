#!/usr/bin/env python3
"""The Alchemist — Semantic Prompt Compiler.

Compiles natural language prompts into token-dense Machine Dialect.
Four-stage pipeline: spell correction → symbolic mapping → stop-word stripping → structural minification.

v2: Hardened against semantic collapse via protected words, code block
detection, lossless symbol escaping, negation-aware matching, and
high-logic heuristic switch.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Escape sentinel — protects literal Unicode symbols in user text
# ---------------------------------------------------------------------------

_ESCAPE_PREFIX = "\x00ESC:"
_ESCAPE_SUFFIX = "\x00"

# Symbols used by our dialect that could appear in user text
_DIALECT_SYMBOLS = {"Σ", "⇒", "∴", "⟺", "Δ", "↗", "↻", "⊂", "ƒ", "→"}

# ---------------------------------------------------------------------------
# Stage 1 data: Symbolic Mapping dictionary
# ---------------------------------------------------------------------------

DIALECT_MAP: dict[str, str] = {
    # --- Filler removal (map to empty string) ---
    "i want you to": "",
    "i would like you to": "",
    "i need you to": "",
    "could you please": "",
    "can you please": "",
    "please note that": "",
    "it should be noted that": "",
    "i'd like you to": "",

    # --- Meta-instructions ---
    "provide a detailed explanation": "Σ++",
    "explain step by step": "CoT→",
    "think step by step": "CoT",
    "chain of thought": "CoT",
    "let's think about this": "CoT",
    "step by step": "CoT",
    "summarize": "Σ",
    "in conclusion": "∴",
    "for example": "e.g.",
    "in other words": "i.e.",
    "as a result": "∴",
    "in summary": "Σ",

    # --- Format instructions ---
    "take this text and turn it into a json object with keys for": "Σ TEXT⇒{}",
    "convert to json": "⇒{}",
    "convert to yaml": "⇒yaml",
    "convert to csv": "⇒csv",
    "format as a table": "⇒table",
    "format as markdown": "⇒md",
    "format as a list": "⇒[]",
    "output as code": "⇒code",
    "return only the code": "⇒code!",
    "output in json format": "⇒{}",
    "respond in json": "⇒{}",
    "as a json object": "⇒{}",
    "as a bullet list": "⇒[]",
    "as a numbered list": "⇒[#]",

    # --- Constraint phrases ---
    "strict adherence to constraints": "!strict",
    "strict adherence": "!strict",
    "do not deviate": "!strict",
    "you must always": "!always",
    "under no circumstances": "!never",
    "do not include": "!omit",
    "make sure to": "!ensure",
    "it is important that": "!ensure",
    "please ensure that": "!ensure",
    "without exception": "!noexcept",
    "do not mention": "!omit",
    "do not explain": "!omit explain",
    "keep it concise": "!brief",
    "be concise": "!brief",
    "be specific": "!specific",

    # --- Role/persona ---
    "you are an expert": "@expert",
    "act as a": "@role:",
    "pretend you are": "@role:",
    "from the perspective of": "@pov:",
    "as an expert in": "@expert:",
    "you are a": "@role:",

    # --- Action verbs ---
    "analyze and provide": "Δ→",
    "compare and contrast": "⟺",
    "translate to": "↗lang:",
    "rewrite the following": "↻",
    "generate a list of": "⇒[]",
    "classify the following": "⊂classify",
    "extract the following": "⊂extract",
    "evaluate whether": "⊂eval",
    "write a function": "ƒ",
    "create a function": "ƒ",
    "implement a": "impl:",
    "refactor the": "↻",
}

# Inverse map for decompilation (skip empty-string mappings)
INVERSE_DIALECT_MAP: dict[str, str] = {
    v: k for k, v in DIALECT_MAP.items() if v
}

# ---------------------------------------------------------------------------
# Negation-sensitive patterns: these DIALECT_MAP keys must NOT match when
# preceded by negation words. We compile separate negation-aware regexes.
# ---------------------------------------------------------------------------

_NEGATION_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "act as a",
    "implement a",
    "you are a",
    "you are an expert",
    "as an expert in",
    "pretend you are",
})

# Words that signal negation in the preceding context (up to 5 words back)
_NEGATION_WORDS: frozenset[str] = frozenset({
    "not", "no", "never", "don't", "doesn't", "didn't", "cannot",
    "can't", "won't", "shouldn't", "mustn't", "isn't", "aren't",
    "wasn't", "weren't", "wouldn't", "haven't", "hasn't", "hadn't",
    "nor", "neither",
})

# ---------------------------------------------------------------------------
# Stage 2 data: Stop-words
# Conservative set — excludes semantically meaningful words
# ---------------------------------------------------------------------------

STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "which", "who", "whom", "these", "those", "am", "its",
    "of", "with", "at", "by", "into",
    "above", "below", "between",
    "off", "over", "under", "again", "further",
    "here", "there", "where",
    "each", "few", "most", "other", "some", "such",
    "same", "very", "just",
})

# Words that LOOK like stop-words but carry semantic weight.
# Never strip these.
PROTECTED_WORDS: frozenset[str] = frozenset({
    # Negation
    "not", "no", "never", "none", "neither", "nor", "nothing",
    "don't", "doesn't", "didn't", "cannot", "can't", "won't",
    "shouldn't", "mustn't", "isn't", "aren't", "wasn't", "weren't",
    "wouldn't", "haven't", "hasn't", "hadn't",
    # Temporal / ordering
    "before", "after", "then", "first", "last", "next", "until", "once",
    "during", "while", "when",
    # Logic / conditional
    "if", "else", "but", "and", "or", "only", "both", "either",
    "because", "so", "than", "though", "although", "unless", "whether",
    # Modality
    "should", "shall", "must", "will", "would", "may", "might",
    "can", "could",
    # Quantity / identity
    "all", "any", "every", "this", "that", "it",
    # Prepositions that carry spatial/relational meaning in instructions
    "to", "from", "in", "on", "for", "as", "out", "through",
    # Code keywords that happen to be English words
    "return", "import", "class", "def", "true", "false", "null",
    "select", "where", "join", "group", "order", "limit", "insert",
    "update", "delete", "create", "drop", "alter", "index",
})

# ---------------------------------------------------------------------------
# Code block detection
# ---------------------------------------------------------------------------

# Patterns that indicate inline code or code blocks
_CODE_FENCE_RE = re.compile(r'```[\s\S]*?```', re.MULTILINE)
_INLINE_CODE_RE = re.compile(r'`[^`]+`')
_CODE_INDICATORS = re.compile(
    r'(?:'
    r'def\s+\w+\s*\(|'          # Python function
    r'class\s+\w+[\s(:]|'       # Class definition
    r'SELECT\s+.+?\s+FROM|'     # SQL
    r'import\s+\w|'             # Import statement
    r'function\s+\w+\s*\(|'     # JS function
    r'(?:const|let|var)\s+\w+|' # JS variables
    r'(?:CREATE|DROP|ALTER|INSERT|UPDATE|DELETE)\s+' # SQL DDL/DML
    r')',
    re.IGNORECASE,
)

_CODE_BLOCK_SENTINEL = "\x00CODE_BLOCK_{}\x00"


# ---------------------------------------------------------------------------
# High-logic heuristic
# ---------------------------------------------------------------------------

_LOGIC_MARKERS = re.compile(
    r'\b('
    r'if\s+and\s+only\s+if|'
    r'if\s+.+?\s+then\s+.+?\s+else|'
    r'but\s+only|'
    r'but\s+not|'
    r'except\s+when|'
    r'unless|'
    r'whereas|'
    r'provided\s+that|'
    r'on\s+the\s+condition|'
    r'iff\b|'
    r'xor\b|'
    r'mutually\s+exclusive|'
    r'necessary\s+and\s+sufficient|'
    r'contrapositive|'
    r'thread.safe|'
    r'race\s+condition|'
    r'deadlock|'
    r'atomic|'
    r'mutex|'
    r'semaphore'
    r')\b',
    re.IGNORECASE,
)


def _compute_logic_density(text: str) -> float:
    """Return 0.0-1.0 score of how logic-heavy a prompt is."""
    words = text.split()
    if not words:
        return 0.0

    markers = len(_LOGIC_MARKERS.findall(text))
    conditionals = len(re.findall(r'\bif\b', text, re.IGNORECASE))
    negations = len(re.findall(r'\bnot\b|\bnever\b|\bno\b', text, re.IGNORECASE))
    ordering = len(re.findall(r'\bfirst\b|\bthen\b|\bbefore\b|\bafter\b|\bnext\b', text, re.IGNORECASE))

    signal = markers * 3 + conditionals * 2 + negations * 2 + ordering
    density = min(signal / len(words), 1.0)
    return density


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens. Uses tiktoken if available, else naive whitespace split."""
    try:
        import tiktoken  # type: ignore[import-untyped]
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except (ImportError, KeyError):
        return len(text.split())


# ---------------------------------------------------------------------------
# Core compiler
# ---------------------------------------------------------------------------

class PromptCompiler:
    """Three-stage semantic prompt compiler with semantic safety guards."""

    def __init__(self) -> None:
        # Sort keys longest-first to prevent partial matches
        sorted_keys = sorted(DIALECT_MAP.keys(), key=len, reverse=True)

        # Precompile one regex per dialect entry
        self._patterns: list[tuple[re.Pattern[str], str, bool]] = []
        for key in sorted_keys:
            neg_sensitive = key in _NEGATION_SENSITIVE_KEYS
            pat = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
            self._patterns.append((pat, DIALECT_MAP[key], neg_sensitive))

        # Stop-word regex — only matches words NOT in PROTECTED_WORDS
        safe_stops = STOP_WORDS - PROTECTED_WORDS
        sorted_stops = sorted(safe_stops, key=len, reverse=True)
        self._stop_re = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in sorted_stops) + r')\b',
            re.IGNORECASE,
        )

        # Whitespace normalization
        self._multispace_re = re.compile(r'[ \t]{2,}')
        self._multiline_re = re.compile(r'\n{3,}')

        # Punctuation normalization (note: dots excluded from repeated_punct
        # because ... is a valid ellipsis that must be preserved)
        self._repeated_punct_re = re.compile(r'([!?])\1{2,}')    # 3+ repeated !/?  → 1
        self._repeated_double_re = re.compile(r'([!?])\1')        # !! or ?? → single
        self._ellipsis_re = re.compile(r'\.{4,}')                 # 4+ dots → ...
        self._space_before_punct_re = re.compile(r'\s+([,.\-:;!?])')

        # Decompile patterns (longest symbol first)
        sorted_symbols = sorted(INVERSE_DIALECT_MAP.keys(), key=len, reverse=True)
        self._decompile_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(re.escape(sym)), INVERSE_DIALECT_MAP[sym])
            for sym in sorted_symbols
        ]

    # ---- Pre-processing: protect code blocks and literal symbols ----

    def _extract_code_blocks(self, text: str) -> tuple[str, dict[str, str]]:
        """Remove code blocks/inline code from text, replacing with sentinels."""
        blocks: dict[str, str] = {}
        counter = 0

        def _stash(m: re.Match[str]) -> str:
            nonlocal counter
            key = _CODE_BLOCK_SENTINEL.format(counter)
            blocks[key] = m.group(0)
            counter += 1
            return key

        # Fenced code blocks first (greedy)
        text = _CODE_FENCE_RE.sub(_stash, text)
        # Inline code
        text = _INLINE_CODE_RE.sub(_stash, text)
        return text, blocks

    def _detect_inline_code(self, text: str) -> tuple[str, dict[str, str]]:
        """Detect un-fenced code segments (after colon patterns like 'Fix this code: ...')."""
        blocks: dict[str, str] = {}
        counter = 1000  # Offset to avoid collision with fenced blocks

        # Pattern: "... code:" or "... query:" or "... pattern:" followed by code-like content to end of line
        colon_code_re = re.compile(
            r'((?:code|query|pattern|regex|command|script|sql|expression)\s*:\s*)(.*?)$',
            re.IGNORECASE | re.MULTILINE,
        )

        def _stash_after_colon(m: re.Match[str]) -> str:
            nonlocal counter
            prefix = m.group(1)
            code_part = m.group(2)
            if _CODE_INDICATORS.search(code_part) or re.search(r'[(){}\[\]<>=;|&^$\\]', code_part):
                key = _CODE_BLOCK_SENTINEL.format(counter)
                blocks[key] = code_part
                counter += 1
                return prefix + key
            return m.group(0)

        text = colon_code_re.sub(_stash_after_colon, text)
        return text, blocks

    def _restore_blocks(self, text: str, blocks: dict[str, str]) -> str:
        """Restore code blocks from sentinels."""
        for key, value in blocks.items():
            text = text.replace(key, value)
        return text

    def _escape_literal_symbols(self, text: str) -> str:
        """Escape dialect symbols that exist in the original user text."""
        for sym in _DIALECT_SYMBOLS:
            if sym in text:
                text = text.replace(sym, f"{_ESCAPE_PREFIX}{sym}{_ESCAPE_SUFFIX}")
        return text

    def _unescape_literal_symbols(self, text: str) -> str:
        """Restore escaped literal symbols."""
        for sym in _DIALECT_SYMBOLS:
            text = text.replace(f"{_ESCAPE_PREFIX}{sym}{_ESCAPE_SUFFIX}", sym)
        return text

    # ---- Pre-compression normalization ----

    def _normalize(self, text: str) -> str:
        """Normalize text before compression.

        Runs after spell correction, before symbolic mapping.
        - Trim whitespace per line
        - Fix sentence-initial capitalization
        - Normalize repeated punctuation (!!!, ???, ....)
        - Remove redundant symbols
        - Collapse multiple spaces
        """
        # Trim whitespace per line
        lines = [line.strip() for line in text.splitlines()]

        # Sentence-initial caps: capitalize first letter after sentence-ending punct
        normalized_lines: list[str] = []
        for line in lines:
            if not line:
                normalized_lines.append(line)
                continue
            # Capitalize first character of line if it's a letter
            if line[0].islower():
                line = line[0].upper() + line[1:]
            # Capitalize after sentence-ending punctuation within the line
            line = re.sub(
                r'([.!?])\s+([a-z])',
                lambda m: m.group(1) + ' ' + m.group(2).upper(),
                line,
            )
            normalized_lines.append(line)

        text = '\n'.join(normalized_lines)

        # Normalize repeated punctuation
        text = self._ellipsis_re.sub('...', text)       # 4+ dots → ...
        text = self._repeated_punct_re.sub(r'\1', text)  # 3+ same → 1
        text = self._repeated_double_re.sub(r'\1', text) # !! → !, ?? → ?

        # Remove space before punctuation
        text = self._space_before_punct_re.sub(r'\1', text)

        # Collapse multiple spaces
        text = self._multispace_re.sub(' ', text)

        # Collapse excessive blank lines
        text = self._multiline_re.sub('\n\n', text)

        return text.strip()

    # ---- Stage 1: Symbolic Mapping ----

    @staticmethod
    def _has_negation_before(text: str, match_start: int) -> bool:
        """Check if any negation word appears in the 5 words before match_start."""
        preceding = text[:match_start].split()
        window = preceding[-5:] if len(preceding) >= 5 else preceding
        return any(w.lower().rstrip(".,;:!?") in _NEGATION_WORDS for w in window)

    def _stage_symbolic(self, text: str, intensity: float) -> str:
        """Apply symbolic mapping. intensity 0.0=skip, 1.0=full."""
        if intensity < 0.1:
            return text
        for pattern, replacement, neg_sensitive in self._patterns:
            if neg_sensitive:
                # Context-aware: skip replacement if negation found nearby
                # Capture both text and replacement via default args
                def _make_replacer(_repl: str, _src: str) -> callable:
                    def _replace(m: re.Match[str]) -> str:
                        if self._has_negation_before(_src, m.start()):
                            return m.group(0)
                        return _repl
                    return _replace
                text = pattern.sub(_make_replacer(replacement, text), text)
            else:
                text = pattern.sub(replacement, text)
        return text

    # ---- Stage 2: Stop-Word Stripping ----

    def _stage_stopwords(self, text: str, intensity: float) -> str:
        """Strip stop words. Reduced set when intensity < 1.0."""
        if intensity < 0.1:
            return text
        text = self._stop_re.sub('', text)
        text = self._multispace_re.sub(' ', text)
        text = re.sub(r' +([,.\-:;!?])', r'\1', text)
        lines = [line.strip() for line in text.splitlines()]
        text = '\n'.join(lines)
        return text.strip()

    # ---- Stage 3: Structural Minification ----

    def _minify_json_blocks(self, text: str) -> str:
        """Find JSON objects/arrays in text and minify them."""
        result = []
        i = 0
        while i < len(text):
            if text[i] in ('{', '['):
                bracket = text[i]
                close = '}' if bracket == '{' else ']'
                depth = 1
                j = i + 1
                while j < len(text) and depth > 0:
                    if text[j] == bracket:
                        depth += 1
                    elif text[j] == close:
                        depth -= 1
                    j += 1
                candidate = text[i:j]
                try:
                    parsed = json.loads(candidate)
                    minified = json.dumps(parsed, separators=(',', ':'))
                    result.append(minified)
                    i = j
                    continue
                except (json.JSONDecodeError, ValueError):
                    pass
            result.append(text[i])
            i += 1
        return ''.join(result)

    def _collapse_lists(self, text: str) -> str:
        """Collapse verbose numbered/bulleted lists into compact form."""
        text = re.sub(r'(\d+)\.\s+', r'\1)', text)
        text = re.sub(r'^[\-\*]\s+', '•', text, flags=re.MULTILINE)
        return text

    def _stage_structural(self, text: str, intensity: float) -> str:
        if intensity < 0.1:
            return text
        text = self._minify_json_blocks(text)
        text = self._collapse_lists(text)
        text = self._multiline_re.sub('\n\n', text)
        text = self._multispace_re.sub(' ', text)
        return text.strip()

    # ---- Public API ----

    def compile(self, prompt: str) -> str:
        """Main compression pipeline. Returns token-dense Machine Dialect.

        Automatically detects high-logic prompts and reduces compression
        intensity to prevent semantic collapse.
        """
        # Pre-process: escape literal dialect symbols in user text
        text = self._escape_literal_symbols(prompt)

        # Pre-process: extract code blocks to protect from compression
        text, fenced_blocks = self._extract_code_blocks(text)
        text, inline_blocks = self._detect_inline_code(text)
        all_blocks = {**fenced_blocks, **inline_blocks}

        # Stage 0: Spell correction (before dialect mapping to avoid
        # corrupting multi-word phrase matches in DIALECT_MAP)
        try:
            from engine.spell import correct_spelling
            text = correct_spelling(text)
        except ImportError:
            try:
                from spell import correct_spelling
                text = correct_spelling(text)
            except Exception:
                pass  # SymSpell not available or failed, skip spell correction
        except Exception:
            pass  # Spell correction failed, continue without it

        # Stage 0b: Normalize (after spell correction, before compression)
        text = self._normalize(text)

        # Compute logic density → adjust compression intensity
        logic_density = _compute_logic_density(prompt)
        # intensity: 1.0 for normal prompts, 0.5 for logic-heavy, 0.0 for ultra-logic
        if logic_density > 0.15:
            intensity = max(0.3, 1.0 - logic_density * 2)
        else:
            intensity = 1.0

        # Three-stage pipeline (after spell correction + normalization)
        text = self._stage_symbolic(text, intensity)
        text = self._stage_stopwords(text, intensity)
        text = self._stage_structural(text, intensity)

        # Post-process: restore code blocks and literal symbols
        text = self._restore_blocks(text, all_blocks)
        text = self._unescape_literal_symbols(text)

        return text

    def decompile(self, compressed: str) -> str:
        """Reverse symbolic mapping for human readability.

        Note: Decompilation is approximate. Stop-word removal and structural
        minification are lossy transforms that cannot be perfectly reversed.
        """
        text = compressed
        for pattern, expansion in self._decompile_patterns:
            text = pattern.sub(expansion, text)
        return text

    def estimate_savings(self, prompt: str) -> dict[str, int | float]:
        """Return token counts and compression statistics."""
        compiled = self.compile(prompt)
        orig_tokens = count_tokens(prompt)
        comp_tokens = count_tokens(compiled)
        saved = orig_tokens - comp_tokens

        return {
            "original_tokens": orig_tokens,
            "compressed_tokens": comp_tokens,
            "saved_tokens": saved,
            "compression_ratio": round(comp_tokens / orig_tokens, 3) if orig_tokens else 1.0,
            "percentage_saved": round((saved / orig_tokens) * 100, 1) if orig_tokens else 0.0,
            "original_chars": len(prompt),
            "compressed_chars": len(compiled),
            "compiled_text": compiled,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_stats(stats: dict[str, int | float]) -> None:
    """Pretty-print compression statistics."""
    print(f"\n{'─' * 50}")
    print("⚗  COMPRESSION REPORT")
    print(f"{'─' * 50}")
    print(f"  Original tokens:   {stats['original_tokens']}")
    print(f"  Compressed tokens: {stats['compressed_tokens']}")
    print(f"  Tokens saved:      {stats['saved_tokens']}")
    print(f"  Compression ratio: {stats['compression_ratio']}")
    print(f"  Savings:           {stats['percentage_saved']}%")
    print(f"  Chars: {stats['original_chars']} → {stats['compressed_chars']}")
    print(f"{'─' * 50}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="alchemist",
        description="The Alchemist — Semantic Prompt Compiler",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", "-p", type=str, help="Prompt text to compile")
    group.add_argument("--file", "-f", type=str, help="File containing prompt text")

    parser.add_argument("--decompile", "-d", action="store_true",
                        help="Decompile compressed text back to natural language")
    parser.add_argument("--no-stats", action="store_true",
                        help="Suppress compression statistics")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    # Read input
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.prompt

    compiler = PromptCompiler()

    if args.decompile:
        result = compiler.decompile(text)
        if args.json:
            print(json.dumps({"decompiled": result}, indent=2))
        else:
            print(result)
        return

    # Compile
    stats = compiler.estimate_savings(text)
    compiled = stats["compiled_text"]

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(compiled)
        if not args.no_stats:
            _print_stats(stats)


if __name__ == "__main__":
    main()
