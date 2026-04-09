#!/usr/bin/env python3
"""AlienTalk REPL — transparent prompt compression for subscription CLIs.

Wraps claude, codex, or any CLI tool with automatic prompt compression.
User types naturally, every message is compressed before reaching the LLM.
"""
from __future__ import annotations

import argparse
try:
    import readline  # noqa: F401 — imported for side effect (input history/editing)
except ImportError:
    pass  # Windows — no readline, history/editing unavailable
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alchemist import PromptCompiler

# ---------------------------------------------------------------------------
# Tiktoken availability check
# ---------------------------------------------------------------------------

_TIKTOKEN_WARNED = False


def _check_tiktoken() -> None:
    """Print a one-time warning if tiktoken is not installed."""
    global _TIKTOKEN_WARNED
    if _TIKTOKEN_WARNED:
        return
    _TIKTOKEN_WARNED = True
    try:
        import tiktoken  # noqa: F401
    except ImportError:
        print(
            "[atk] tiktoken not installed — token counts are word-count estimates. "
            "Install with: pip install tiktoken",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Backend definitions
# ---------------------------------------------------------------------------

BACKENDS: dict[str, dict[str, list[str]]] = {
    "claude": {"first": ["claude", "-p"], "cont": ["claude", "-p", "--continue"]},
    "codex": {"first": ["codex", "exec"], "cont": ["codex", "exec"]},
}

# ---------------------------------------------------------------------------
# Stats normalization
# ---------------------------------------------------------------------------


def normalize_stats(stats: dict) -> dict[str, int | float | str]:
    """Normalize stats from PromptCompiler or AlchemistPrime to a common shape.

    PromptCompiler returns: original_tokens, compressed_tokens, percentage_saved, compiled_text
    AlchemistPrime returns: input_original, input_compressed, input_saved_pct, compiled_text
    """
    return {
        "original_tokens": stats.get("original_tokens", stats.get("input_original", 0)),
        "compressed_tokens": stats.get("compressed_tokens", stats.get("input_compressed", 0)),
        "percentage_saved": stats.get("percentage_saved", stats.get("input_saved_pct", 0.0)),
        "compiled_text": stats.get("compiled_text", ""),
    }


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def read_prompt() -> str | None:
    """Read a single line of user input with readline. Returns None on EOF."""
    try:
        line = input("you> ")
    except EOFError:
        return None
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return None
    stripped = line.strip()
    if not stripped:
        return ""  # empty input, caller should skip
    return stripped


# ---------------------------------------------------------------------------
# Backend execution
# ---------------------------------------------------------------------------

_TIMEOUT = 120  # seconds


def run_backend(
    cmd: list[str], prompt: str, extra_args: list[str], quiet: bool
) -> str | None:
    """Run backend CLI command with the compressed prompt. Returns stdout or None on error.

    Uses list-mode subprocess (no shell=True) to prevent injection.
    """
    full_cmd = cmd + [prompt] + extra_args

    # Show a thinking indicator
    stop_event = threading.Event()
    if not quiet:
        def _spinner() -> None:
            print("Thinking...", end="", file=sys.stderr, flush=True)
            stop_event.wait()
            print("\r           \r", end="", file=sys.stderr, flush=True)

        t = threading.Thread(target=_spinner, daemon=True)
        t.start()

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        stop_event.set()
        print(
            f"[atk] error: '{cmd[0]}' not found. Is it installed and on your PATH?",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        stop_event.set()
        print(
            f"[atk] error: backend timed out after {_TIMEOUT}s",
            file=sys.stderr,
        )
        return None
    except OSError as e:
        stop_event.set()
        print(f"[atk] error: {e}", file=sys.stderr)
        return None
    finally:
        stop_event.set()
        if not quiet:
            t.join()

    if result.returncode != 0:
        stderr_msg = result.stderr.strip()
        print(
            f"[atk] backend error (exit {result.returncode}): {stderr_msg}",
            file=sys.stderr,
        )
        return None

    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="alientalk-repl",
        description="AlienTalk REPL — transparent prompt compression for subscription CLIs",
    )
    parser.add_argument(
        "--backend", "-b",
        default="claude",
        choices=list(BACKENDS.keys()),
        help="Backend CLI to use (default: claude)",
    )
    parser.add_argument(
        "--prime",
        action="store_true",
        help="Use AlchemistPrime for heavier compression",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress compression stats",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Extra arguments passed through to the backend CLI (place after --)",
    )

    args = parser.parse_args()

    # Initialize compiler
    if args.prime:
        from alchemist_prime import AlchemistPrime
        compiler = AlchemistPrime(echo=False)
    else:
        compiler = PromptCompiler()

    backend = BACKENDS[args.backend]

    # Tiktoken check (one-time)
    _check_tiktoken()

    # Banner
    print(
        f"AlienTalk REPL — compression active, backend: {args.backend}",
        file=sys.stderr,
    )
    if args.backend == "claude":
        print(
            "Note: --continue resumes the last Claude session. "
            "Parallel Claude sessions may interfere.",
            file=sys.stderr,
        )
    print("Type your prompt. Ctrl+D to exit.\n", file=sys.stderr)

    turn = 0
    total_original = 0
    total_compressed = 0

    while True:
        prompt = read_prompt()
        if prompt is None:
            break
        if prompt == "":
            continue  # skip empty input

        # Compress
        try:
            stats = normalize_stats(compiler.estimate_savings(prompt))
        except Exception as e:
            print(f"[atk] compression error: {e}", file=sys.stderr)
            continue
        compressed = stats["compiled_text"]

        # Print stats
        if not args.quiet:
            print(
                f"[atk] {stats['original_tokens']}→{stats['compressed_tokens']} "
                f"tokens ({stats['percentage_saved']}% saved)",
                file=sys.stderr,
            )

        # Dispatch to backend
        cmd = backend["cont"] if turn > 0 else backend["first"]
        response = run_backend(cmd, compressed, args.extra_args, args.quiet)
        if response is not None:
            print(response)
            print()  # blank line between response and next prompt
            turn += 1
            total_original += stats["original_tokens"]
            total_compressed += stats["compressed_tokens"]

    # Session summary
    if turn > 0 and not args.quiet:
        pct = round((1 - total_compressed / total_original) * 100, 1) if total_original else 0.0
        print(
            f"\nSession: {total_original}→{total_compressed} tokens "
            f"({pct}% saved across {turn} messages)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
