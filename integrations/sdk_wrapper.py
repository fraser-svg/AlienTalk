#!/usr/bin/env python3
"""Drop-in Anthropic SDK wrapper that auto-compiles prompts through AlienTalk.

Usage:
    # Instead of:
    #   from anthropic import Anthropic
    # Use:
    from integrations.sdk_wrapper import AlienTalkClient

    client = AlienTalkClient()  # same args as Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Your verbose prompt here..."}],
    )
    # Prompt was auto-compressed before reaching the API.
    # Response is auto-expanded if echo mode is on.

    # Access compression stats from the last call:
    print(client.last_stats)

Configuration:
    client = AlienTalkClient(
        echo=True,          # Append echo directive (default: True)
        min_tokens=20,      # Skip compression for short prompts (default: 20)
        verbose=False,      # Print compression stats to stderr (default: False)
    )
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory so alchemist imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from alchemist import count_tokens
from alchemist_prime import AlchemistPrime


class _AlchemistMessages:
    """Wraps anthropic.Messages to auto-compile prompts."""

    def __init__(self, messages_api: anthropic.resources.Messages,
                 prime: AlchemistPrime, min_tokens: int, verbose: bool,
                 parent: AlienTalkClient) -> None:
        self._api = messages_api
        self._prime = prime
        self._min_tokens = min_tokens
        self._verbose = verbose
        self._parent = parent

    def _compile_messages(self, messages: list[dict]) -> list[dict]:
        """Compile user messages through Alchemist Prime."""
        compiled = []
        stats = {"original_tokens": 0, "compressed_tokens": 0, "messages_compiled": 0}

        for msg in messages:
            if msg["role"] == "user" and isinstance(msg["content"], str):
                original = msg["content"]
                orig_tokens = count_tokens(original)

                if orig_tokens >= self._min_tokens:
                    compressed = self._prime.compile(original)
                    comp_tokens = count_tokens(compressed)
                    stats["original_tokens"] += orig_tokens
                    stats["compressed_tokens"] += comp_tokens
                    stats["messages_compiled"] += 1
                    compiled.append({"role": "user", "content": compressed})
                else:
                    stats["original_tokens"] += orig_tokens
                    stats["compressed_tokens"] += orig_tokens
                    compiled.append(msg)
            else:
                compiled.append(msg)

        if stats["original_tokens"] > 0:
            stats["percentage_saved"] = round(
                (1 - stats["compressed_tokens"] / stats["original_tokens"]) * 100, 1
            )
        else:
            stats["percentage_saved"] = 0.0

        self._parent.last_stats = stats

        if self._verbose and stats["messages_compiled"] > 0:
            print(
                f"[alchemist] {stats['original_tokens']}→{stats['compressed_tokens']} "
                f"tokens ({stats['percentage_saved']}% saved)",
                file=sys.stderr,
            )

        return compiled

    def create(self, **kwargs) -> anthropic.types.Message:
        """Create a message with auto-compiled prompts."""
        if "messages" in kwargs:
            kwargs["messages"] = self._compile_messages(kwargs["messages"])
        return self._api.create(**kwargs)

    def stream(self, **kwargs):
        """Stream a message with auto-compiled prompts."""
        if "messages" in kwargs:
            kwargs["messages"] = self._compile_messages(kwargs["messages"])
        return self._api.stream(**kwargs)

    def __getattr__(self, name):
        return getattr(self._api, name)


class AlienTalkClient:
    """Drop-in replacement for anthropic.Anthropic with auto-compression.

    All standard Anthropic client args are passed through. Additional args
    control Alchemist behavior.
    """

    def __init__(self, *, echo: bool = True, min_tokens: int = 20,
                 verbose: bool = False, **anthropic_kwargs) -> None:
        self._client = anthropic.Anthropic(**anthropic_kwargs)
        self._prime = AlchemistPrime(echo=echo)
        self._min_tokens = min_tokens
        self._verbose = verbose
        self.last_stats: dict = {}

        self.messages = _AlchemistMessages(
            self._client.messages,
            self._prime,
            self._min_tokens,
            self._verbose,
            self,
        )

    @property
    def prime(self) -> AlchemistPrime:
        """Access the underlying AlchemistPrime instance."""
        return self._prime

    def expand_response(self, text: str) -> str:
        """Expand a compressed echo response to natural language."""
        return self._prime.expand_response(text)

    def __getattr__(self, name):
        return getattr(self._client, name)
