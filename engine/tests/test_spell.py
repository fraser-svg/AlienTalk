"""Tests for spell correction layer.

Covers: SymSpell integration, tech allowlist, skip patterns,
DIALECT_MAP misspelling matrix, and pipeline integration.
"""

import pytest

from spell import SpellCorrector, TECH_ALLOWLIST, correct_spelling
from alchemist import PromptCompiler, DIALECT_MAP


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def corrector() -> SpellCorrector:
    return SpellCorrector()


@pytest.fixture(scope="module")
def compiler() -> PromptCompiler:
    return PromptCompiler()


# ---------------------------------------------------------------------------
# Basic spell correction
# ---------------------------------------------------------------------------

class TestBasicCorrection:
    """Common misspellings in prompt-writing context."""

    @pytest.mark.parametrize("misspelled,expected", [
        ("summerize", "summarize"),
        ("explan", "explain"),
        ("implment", "implement"),
        ("genrate", "generate"),
        ("analize", "analyze"),
        ("optmize", "optimize"),
        ("catgorize", "categorize"),
        ("synthasize", "synthesize"),
        ("decribe", "describe"),
        ("compre", "compare"),
        ("evalute", "evaluate"),
        ("translte", "translate"),
    ])
    def test_prompt_domain_corrections(self, corrector: SpellCorrector, misspelled: str, expected: str) -> None:
        result = corrector.correct_word(misspelled)
        assert result == expected, f"{misspelled} → {result}, expected {expected}"

    def test_already_correct_word(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("summarize") == "summarize"
        assert corrector.correct_word("explain") == "explain"

    def test_preserves_title_case(self, corrector: SpellCorrector) -> None:
        result = corrector.correct_word("Summerize")
        assert result == "Summarize"

    def test_preserves_upper_case(self, corrector: SpellCorrector) -> None:
        # Short all-caps words should be skipped (acronyms)
        assert corrector.correct_word("API") == "API"

    def test_preserves_trailing_punctuation(self, corrector: SpellCorrector) -> None:
        result = corrector.correct_word("summerize.")
        assert result == "summarize."

    def test_preserves_leading_punctuation(self, corrector: SpellCorrector) -> None:
        result = corrector.correct_word("(summerize)")
        assert result == "(summarize)"


# ---------------------------------------------------------------------------
# Tech allowlist
# ---------------------------------------------------------------------------

class TestTechAllowlist:
    """Tech words should survive spell correction unchanged."""

    @pytest.mark.parametrize("word", [
        "kubectl", "kubernetes", "pytorch", "terraform", "nginx",
        "webpack", "fastapi", "django", "pytest", "tokio",
        "pyo3", "graphql", "elasticsearch", "postgresql", "redis",
        "docker", "ansible", "prometheus", "nextjs", "tailwindcss",
    ])
    def test_tech_word_preserved(self, corrector: SpellCorrector, word: str) -> None:
        assert corrector.correct_word(word) == word

    def test_allowlist_has_minimum_size(self) -> None:
        assert len(TECH_ALLOWLIST) >= 500

    def test_tech_word_in_sentence(self, corrector: SpellCorrector) -> None:
        text = "Deploy the pytorch model to kubernetes using kubectl"
        corrected = corrector.correct_text(text)
        assert "pytorch" in corrected
        assert "kubernetes" in corrected
        assert "kubectl" in corrected


# ---------------------------------------------------------------------------
# Skip patterns
# ---------------------------------------------------------------------------

class TestSkipPatterns:
    """Protected patterns should be left unchanged."""

    @pytest.mark.parametrize("word", [
        "myVariable",       # camelCase
        "MyComponent",      # PascalCase (with mixed case)
        "snake_case_var",   # snake_case
        "SCREAMING_CASE",   # SCREAMING_SNAKE
        "$variable",        # $-prefixed
        "@decorator",       # @-prefixed
        "#channel",         # #-prefixed
        "--verbose",        # CLI long flag
        "-v",               # CLI short flag
    ])
    def test_variable_names_skipped(self, corrector: SpellCorrector, word: str) -> None:
        assert corrector.correct_word(word) == word

    def test_urls_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("https://example.com") == "https://example.com"

    def test_emails_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("user@test.com") == "user@test.com"

    def test_paths_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("./src/main.py") == "./src/main.py"
        assert corrector.correct_word("~/config.json") == "~/config.json"

    def test_words_with_digits_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("python3") == "python3"
        assert corrector.correct_word("v2") == "v2"
        assert corrector.correct_word("abc123") == "abc123"

    def test_acronyms_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("API") == "API"
        assert corrector.correct_word("GPU") == "GPU"
        assert corrector.correct_word("CPU") == "CPU"

    def test_single_chars_skipped(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_word("a") == "a"
        assert corrector.correct_word("x") == "x"

    def test_code_sentinel_skipped(self, corrector: SpellCorrector) -> None:
        sentinel = "\x00CODE_BLOCK_42\x00"
        assert corrector.correct_word(sentinel) == sentinel


# ---------------------------------------------------------------------------
# Full text correction
# ---------------------------------------------------------------------------

class TestFullText:
    """End-to-end text correction."""

    def test_sentence_with_misspellings(self, corrector: SpellCorrector) -> None:
        text = "Plese summerize the document and explan the key points"
        corrected = corrector.correct_text(text)
        assert "Please" in corrected
        assert "summarize" in corrected
        assert "explain" in corrected

    def test_preserves_whitespace(self, corrector: SpellCorrector) -> None:
        text = "word1  word2\tword3\nword4"
        corrected = corrector.correct_text(text)
        # Whitespace structure should be preserved
        assert "  " in corrected
        assert "\t" in corrected
        assert "\n" in corrected

    def test_mixed_tech_and_misspellings(self, corrector: SpellCorrector) -> None:
        text = "Explan how to deploi a pytorch model using kubernetes"
        corrected = corrector.correct_text(text)
        assert "pytorch" in corrected
        assert "kubernetes" in corrected
        assert "Explain" in corrected

    def test_empty_string(self, corrector: SpellCorrector) -> None:
        assert corrector.correct_text("") == ""

    def test_all_correct(self, corrector: SpellCorrector) -> None:
        text = "Please summarize the document"
        assert corrector.correct_text(text) == text


# ---------------------------------------------------------------------------
# DIALECT_MAP misspelling matrix
# ---------------------------------------------------------------------------

class TestDialectMapMisspellings:
    """For each DIALECT_MAP key, generate misspellings and verify
    SymSpell + compression produces correct output.

    The critical ordering: spell correct BEFORE dialect mapping.
    A misspelled "summerize" should be corrected to "summarize",
    then compressed to "Σ".
    """

    @pytest.mark.parametrize("misspelled_phrase,expected_symbol", [
        # "summarize" → Σ
        ("summerize this text", "Σ"),
        ("sumarize this text", "Σ"),
        # "explain step by step" → CoT→
        ("explan step by step how", "CoT→"),
        # "provide a detailed explanation" → Σ++
        ("provide a detailed explantion of", "Σ++"),
        ("provide a detaled explanation of", "Σ++"),
    ])
    def test_misspelled_dialect_key_still_compresses(
        self, compiler: PromptCompiler, misspelled_phrase: str, expected_symbol: str
    ) -> None:
        compiled = compiler.compile(misspelled_phrase)
        assert expected_symbol in compiled, (
            f"Expected '{expected_symbol}' in compiled output.\n"
            f"  Input:  {misspelled_phrase}\n"
            f"  Output: {compiled}"
        )


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Spell correction integrates correctly in the full pipeline."""

    def test_code_blocks_protected_from_spell_correction(self, compiler: PromptCompiler) -> None:
        prompt = "Fix this code: ```python\ndef summerize_data():\n    pass\n```"
        compiled = compiler.compile(prompt)
        # Code block content should NOT be spell-corrected
        assert "summerize_data" in compiled

    def test_inline_code_protected(self, compiler: PromptCompiler) -> None:
        prompt = "The function `summerize()` needs fixing"
        compiled = compiler.compile(prompt)
        assert "summerize" in compiled  # Inside backticks, should be preserved

    def test_correction_before_compression(self, compiler: PromptCompiler) -> None:
        """Verify ordering: spell correct first, then compress."""
        # "summerize" misspelling should be corrected to "summarize",
        # then "summarize" should be mapped to "Σ"
        prompt = "Please summerize the following text for me"
        compiled = compiler.compile(prompt)
        assert "Σ" in compiled
        assert "summerize" not in compiled.lower()

    def test_tech_words_survive_full_pipeline(self, compiler: PromptCompiler) -> None:
        prompt = "Explain how pytorch and tensorflow differ for training transformers"
        compiled = compiler.compile(prompt)
        assert "pytorch" in compiled
        assert "tensorflow" in compiled
        assert "transformers" in compiled

    def test_urls_survive_full_pipeline(self, compiler: PromptCompiler) -> None:
        prompt = "Summarize the content at https://example.com/api/docs"
        compiled = compiler.compile(prompt)
        assert "https://example.com/api/docs" in compiled


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

class TestConvenienceFunction:
    def test_correct_spelling_function(self) -> None:
        result = correct_spelling("Plese explan this")
        assert "Please" in result
        assert "explain" in result
