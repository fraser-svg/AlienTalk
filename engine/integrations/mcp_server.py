#!/usr/bin/env python3
"""AlienTalk MCP Server — Prompt optimization tools for MCP-compatible IDEs.

Exposes compile() and estimate_savings() as MCP tools for Claude Code,
Cursor, and other MCP-compatible clients. Zero install beyond the Python
engine and its dependencies.

Usage:
    # Start the MCP server (stdio transport)
    python -m engine.integrations.mcp_server

    # Or from the engine directory
    python integrations/mcp_server.py

    # Configure in your MCP client (e.g., Claude Code settings):
    # {
    #   "mcpServers": {
    #     "alientalk": {
    #       "command": "python",
    #       "args": ["-m", "engine.integrations.mcp_server"]
    #     }
    #   }
    # }
"""
from __future__ import annotations

import sys
import os

# Add engine to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "AlienTalk",
    instructions="Semantic prompt compression. Optimize prompts for speed and token efficiency.",
)


def _get_compiler():
    """Lazy-load PromptCompiler to avoid import cost on startup."""
    try:
        from engine.alchemist import PromptCompiler
    except ImportError:
        from alchemist import PromptCompiler
    return PromptCompiler()


# Cache compiler instance
_compiler = None


def _compiler_instance():
    global _compiler
    if _compiler is None:
        _compiler = _get_compiler()
    return _compiler


@mcp.tool()
def compile(prompt: str) -> str:
    """Compress a prompt into token-dense Machine Dialect.

    Takes natural language prompt text and applies semantic compression:
    spell correction, symbolic mapping, stop-word stripping, and structural
    minification. Code blocks and technical terms are preserved.

    Returns the compressed prompt text ready to send to an AI model.
    The compressed text produces equivalent AI responses while using
    fewer tokens for faster processing.
    """
    compiler = _compiler_instance()
    return compiler.compile(prompt)


@mcp.tool()
def estimate_savings(prompt: str) -> dict:
    """Estimate token savings from compressing a prompt.

    Returns compression statistics including original and compressed
    token counts, savings percentage, and the compressed text.

    Use this to preview compression results before applying them.
    """
    compiler = _compiler_instance()
    stats = compiler.estimate_savings(prompt)
    # Convert any non-serializable types
    return {
        "original_tokens": int(stats["original_tokens"]),
        "compressed_tokens": int(stats["compressed_tokens"]),
        "saved_tokens": int(stats["saved_tokens"]),
        "compression_ratio": float(stats["compression_ratio"]),
        "percentage_saved": float(stats["percentage_saved"]),
        "compressed_text": str(stats["compiled_text"]),
    }


if __name__ == "__main__":
    mcp.run()
