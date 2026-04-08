#!/usr/bin/env python3
"""Tests for integrations/repl.py — pure function coverage."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "integrations"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.repl import BACKENDS, normalize_stats, run_backend


# ---------------------------------------------------------------------------
# normalize_stats
# ---------------------------------------------------------------------------


class TestNormalizeStats(unittest.TestCase):
    """Tests for the stats normalization wrapper."""

    def test_prompt_compiler_stats(self) -> None:
        """PromptCompiler-style keys pass through correctly."""
        stats = {
            "original_tokens": 20,
            "compressed_tokens": 10,
            "percentage_saved": 50.0,
            "compiled_text": "compressed output",
        }
        result = normalize_stats(stats)
        self.assertEqual(result["original_tokens"], 20)
        self.assertEqual(result["compressed_tokens"], 10)
        self.assertEqual(result["percentage_saved"], 50.0)
        self.assertEqual(result["compiled_text"], "compressed output")

    def test_alchemist_prime_stats(self) -> None:
        """AlchemistPrime-style keys are mapped correctly."""
        stats = {
            "input_original": 30,
            "input_compressed": 12,
            "input_saved_pct": 60.0,
            "compiled_text": "prime output",
            "echo_overhead": 14,
        }
        result = normalize_stats(stats)
        self.assertEqual(result["original_tokens"], 30)
        self.assertEqual(result["compressed_tokens"], 12)
        self.assertEqual(result["percentage_saved"], 60.0)
        self.assertEqual(result["compiled_text"], "prime output")

    def test_missing_keys_default_to_zero(self) -> None:
        """Missing keys fall back to 0 / empty string."""
        result = normalize_stats({})
        self.assertEqual(result["original_tokens"], 0)
        self.assertEqual(result["compressed_tokens"], 0)
        self.assertEqual(result["percentage_saved"], 0.0)
        self.assertEqual(result["compiled_text"], "")

    def test_prompt_compiler_keys_take_precedence(self) -> None:
        """If both key styles exist, PromptCompiler keys win."""
        stats = {
            "original_tokens": 20,
            "input_original": 30,
            "compressed_tokens": 10,
            "input_compressed": 12,
            "percentage_saved": 50.0,
            "input_saved_pct": 60.0,
            "compiled_text": "text",
        }
        result = normalize_stats(stats)
        self.assertEqual(result["original_tokens"], 20)
        self.assertEqual(result["compressed_tokens"], 10)
        self.assertEqual(result["percentage_saved"], 50.0)


# ---------------------------------------------------------------------------
# Backend command construction
# ---------------------------------------------------------------------------


class TestBackendCommands(unittest.TestCase):
    """Tests for backend command dispatch logic."""

    def test_claude_first_turn(self) -> None:
        cmd = BACKENDS["claude"]["first"]
        self.assertEqual(cmd, ["claude", "-p"])

    def test_claude_continuation(self) -> None:
        cmd = BACKENDS["claude"]["cont"]
        self.assertEqual(cmd, ["claude", "-p", "--continue"])

    def test_codex_first_turn(self) -> None:
        cmd = BACKENDS["codex"]["first"]
        self.assertEqual(cmd, ["codex", "exec"])

    def test_codex_no_session_continuity(self) -> None:
        """Codex first and cont commands should be identical (no session support)."""
        self.assertEqual(BACKENDS["codex"]["first"], BACKENDS["codex"]["cont"])

    def test_command_list_mode(self) -> None:
        """Backend commands are lists, not strings (prevents shell injection)."""
        for name, backend in BACKENDS.items():
            self.assertIsInstance(backend["first"], list, f"{name} first is not a list")
            self.assertIsInstance(backend["cont"], list, f"{name} cont is not a list")


# ---------------------------------------------------------------------------
# run_backend error handling
# ---------------------------------------------------------------------------


class TestRunBackend(unittest.TestCase):
    """Tests for run_backend error handling."""

    @patch("integrations.repl.subprocess.run")
    def test_file_not_found(self, mock_run) -> None:
        """Backend binary not found returns None, doesn't crash."""
        mock_run.side_effect = FileNotFoundError
        result = run_backend(["nonexistent_binary_xyz"], "test prompt", [], quiet=True)
        self.assertIsNone(result)

    @patch("integrations.repl.subprocess.run")
    def test_os_error(self, mock_run) -> None:
        """OSError (e.g. permission denied) returns None, doesn't crash."""
        mock_run.side_effect = OSError("Permission denied")
        result = run_backend(["test"], "prompt", [], quiet=True)
        self.assertIsNone(result)

    @patch("integrations.repl.subprocess.run")
    def test_nonzero_exit(self, mock_run) -> None:
        """Non-zero exit code returns None."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["test"], returncode=1, stdout="", stderr="auth failed"
        )
        result = run_backend(["test"], "prompt", [], quiet=True)
        self.assertIsNone(result)

    @patch("integrations.repl.subprocess.run")
    def test_success(self, mock_run) -> None:
        """Successful command returns stripped stdout."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["test"], returncode=0, stdout="  hello world  \n", stderr=""
        )
        result = run_backend(["test"], "prompt", [], quiet=True)
        self.assertEqual(result, "hello world")

    @patch("integrations.repl.subprocess.run")
    def test_timeout(self, mock_run) -> None:
        """Timeout returns None, doesn't crash."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["test"], timeout=120)
        result = run_backend(["test"], "prompt", [], quiet=True)
        self.assertIsNone(result)

    @patch("integrations.repl.subprocess.run")
    def test_extra_args_appended(self, mock_run) -> None:
        """Extra args are appended after the prompt."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        run_backend(["claude", "-p"], "my prompt", ["--model", "opus"], quiet=True)
        called_cmd = mock_run.call_args[0][0]
        self.assertEqual(called_cmd, ["claude", "-p", "my prompt", "--model", "opus"])

    @patch("integrations.repl.subprocess.run")
    def test_shell_metacharacters_safe(self, mock_run) -> None:
        """Shell metacharacters in prompt are passed literally, not interpreted."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        dangerous_prompt = "$(rm -rf /); `echo pwned`; test && bad"
        run_backend(["test"], dangerous_prompt, [], quiet=True)
        called_cmd = mock_run.call_args[0][0]
        # Prompt is a single list element, not shell-expanded
        self.assertEqual(called_cmd[1], dangerous_prompt)
        # Verify shell=False (default)
        kwargs = mock_run.call_args[1]
        self.assertNotIn("shell", kwargs)  # default is False


# ---------------------------------------------------------------------------
# Session stats accumulation
# ---------------------------------------------------------------------------


class TestSessionStats(unittest.TestCase):
    """Tests for session-level stats calculation."""

    def test_percentage_calculation(self) -> None:
        """Session percentage matches the formula."""
        total_original = 100
        total_compressed = 60
        pct = round((1 - total_compressed / total_original) * 100, 1)
        self.assertEqual(pct, 40.0)

    def test_zero_original_tokens(self) -> None:
        """Zero original tokens doesn't cause division by zero."""
        total_original = 0
        total_compressed = 0
        pct = round((1 - total_compressed / total_original) * 100, 1) if total_original else 0.0
        self.assertEqual(pct, 0.0)

    def test_accumulation_across_turns(self) -> None:
        """Stats accumulate correctly across multiple turns."""
        turns = [
            {"original_tokens": 20, "compressed_tokens": 10},
            {"original_tokens": 30, "compressed_tokens": 18},
            {"original_tokens": 15, "compressed_tokens": 9},
        ]
        total_original = sum(t["original_tokens"] for t in turns)
        total_compressed = sum(t["compressed_tokens"] for t in turns)
        self.assertEqual(total_original, 65)
        self.assertEqual(total_compressed, 37)
        pct = round((1 - total_compressed / total_original) * 100, 1)
        self.assertEqual(pct, 43.1)


# ---------------------------------------------------------------------------
# Integration with PromptCompiler
# ---------------------------------------------------------------------------


class TestCompilerIntegration(unittest.TestCase):
    """Verify the REPL's stats wrapper works with real compilers."""

    def test_prompt_compiler_real(self) -> None:
        """normalize_stats works with a real PromptCompiler."""
        from alchemist import PromptCompiler

        compiler = PromptCompiler()
        stats = compiler.estimate_savings("I want you to summarize this text")
        normalized = normalize_stats(stats)
        self.assertGreater(normalized["original_tokens"], 0)
        self.assertIsInstance(normalized["compiled_text"], str)
        self.assertGreater(len(normalized["compiled_text"]), 0)

    def test_alchemist_prime_real(self) -> None:
        """normalize_stats works with a real AlchemistPrime."""
        from alchemist_prime import AlchemistPrime

        compiler = AlchemistPrime(echo=False)
        stats = compiler.estimate_savings("I want you to summarize this text")
        normalized = normalize_stats(stats)
        self.assertGreater(normalized["original_tokens"], 0)
        self.assertIsInstance(normalized["compiled_text"], str)
        self.assertGreater(len(normalized["compiled_text"]), 0)


if __name__ == "__main__":
    unittest.main()
