#!/usr/bin/env python3
"""Test scenarios for The Alchemist — Semantic Prompt Compiler."""
from alchemist import PromptCompiler

SCENARIO_A = """\
You are an expert marketing strategist with over 20 years of experience in digital \
brand building. I want you to summarize the following marketing brief and provide a \
detailed explanation of the key strategic pillars.

Our company, NovaTech Solutions, is launching a new AI-powered productivity suite \
targeting enterprise clients in the Fortune 500. The product suite includes three \
core modules: an intelligent document processor, a meeting summarizer, and a \
workflow automation engine.

Please ensure that your analysis covers the following areas:

1. Target Audience Segmentation: Identify and describe the primary, secondary, and \
tertiary audience segments. It is important that you consider both the decision makers \
(C-suite executives, VP of Engineering, CTO) and the end users (project managers, \
team leads, individual contributors). Under no circumstances should you ignore the \
mid-market segment as a potential growth vector.

2. Competitive Landscape: Compare and contrast our positioning against the top five \
competitors in the AI productivity space. Format as a table with columns for company \
name, primary offering, pricing tier, market share estimate, and key differentiator. \
Make sure to include both direct competitors (Microsoft Copilot, Google Duet AI, \
Notion AI) and indirect competitors (legacy enterprise tools like SAP, Oracle).

3. Channel Strategy: I would like you to analyze and provide recommendations for \
distribution across the following channels:
- Direct enterprise sales (outbound SDR team)
- Partnership channel (SI partners, consultancies)
- Product-led growth (freemium tier for teams under 50)
- Content marketing (thought leadership, whitepapers, webinars)

4. Messaging Framework: Generate a list of five key value propositions, each with a \
headline, supporting copy (2-3 sentences), and a suggested call-to-action. Think step \
by step about how each message maps to a specific audience segment and buying stage. \
Be concise but do not sacrifice clarity. Strict adherence to our brand voice guidelines \
is required: professional yet approachable, data-driven, and forward-looking.

5. Budget Allocation: Provide a recommended Q3 budget split across the channels listed \
above. Output in JSON format with keys for channel_name, percentage_allocation, \
estimated_spend_usd, and expected_roi_multiplier. For example:
{"channel_name": "Direct Sales", "percentage_allocation": 35, "estimated_spend_usd": 875000, "expected_roi_multiplier": 3.2}

In conclusion, the deliverable should be a comprehensive strategic document that our \
leadership team can use to align on go-to-market priorities before the Q3 board meeting. \
Do not include any speculative market data — only use publicly available benchmarks and \
cite your sources where possible. Without exception, all recommendations must be \
actionable within a 90-day execution window.
"""

SCENARIO_B = """\
Act as a senior Python developer with deep expertise in distributed systems and API \
design. I need you to implement a high-performance rate limiter middleware for a \
FastAPI application.

Think step by step about the architecture before writing any code. The requirements are:

1. Token Bucket Algorithm: Write a function that implements a token bucket rate limiter \
with configurable parameters:
- max_tokens: Maximum number of tokens in the bucket (default: 100)
- refill_rate: Tokens added per second (default: 10)
- refill_interval: How often tokens are refilled in seconds (default: 1.0)

2. Storage Backend: Create a function that abstracts the storage layer. It is important \
that you support both:
- In-memory storage using a dictionary (for single-instance deployments)
- Redis-based storage (for distributed deployments across multiple instances)
The interface should be identical regardless of backend. Do not deviate from the \
abstract base class pattern.

3. Middleware Integration: Implement a FastAPI middleware class that:
- Extracts the client identifier from the request (API key header, IP address, or JWT claim)
- Checks the rate limit before processing the request
- Returns a 429 Too Many Requests response with appropriate headers when limit exceeded
- Headers must include: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- You must always include a Retry-After header in 429 responses

4. Configuration: Convert to JSON the following configuration schema and use it for \
runtime configuration:
{
    "default_limits": {
        "anonymous": {"max_tokens": 20, "refill_rate": 2},
        "authenticated": {"max_tokens": 100, "refill_rate": 10},
        "premium": {"max_tokens": 1000, "refill_rate": 100}
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "key_prefix": "ratelimit:"
    },
    "bypass_keys": ["internal-service-key-001", "admin-override-key"]
}

5. Testing: Generate a list of test cases that cover:
- Normal operation (requests within limit)
- Rate limit exceeded scenario
- Token refill behavior over time
- Concurrent request handling
- Redis failover to in-memory fallback
- Bypass key functionality

Return only the code with comprehensive docstrings. Strict adherence to PEP 8 and \
type annotations throughout. Do not include any placeholder or TODO comments — every \
function must be fully implemented. Make sure to handle edge cases like clock skew \
in distributed environments and Redis connection failures gracefully.

Please ensure that the code is production-ready and can be dropped into an existing \
FastAPI project without modification. Be specific about the Python version requirements \
(3.10+) and list all third-party dependencies needed.
"""


def run_scenario(name: str, prompt: str) -> None:
    compiler = PromptCompiler()
    stats = compiler.estimate_savings(prompt)
    compiled = stats["compiled_text"]
    decompiled = compiler.decompile(compiled)

    print(f"\n{'═' * 60}")
    print(f"  {name}")
    print(f"{'═' * 60}")

    # Original (truncated)
    preview = prompt[:300].replace('\n', ' ')
    print(f"\n  ORIGINAL ({stats['original_tokens']} tokens, {stats['original_chars']} chars):")
    print(f"  {preview}...")

    # Compiled
    print(f"\n  COMPILED ({stats['compressed_tokens']} tokens, {stats['compressed_chars']} chars):")
    print(f"  {compiled}")

    # Stats
    print(f"\n  SAVINGS: {stats['saved_tokens']} tokens ({stats['percentage_saved']}%)")
    print(f"  RATIO:   {stats['compression_ratio']}")

    # Decompiled
    print(f"\n  DECOMPILED (lossy):")
    decompile_preview = decompiled[:400].replace('\n', ' ')
    print(f"  {decompile_preview}...")


def main() -> None:
    print("⚗  THE ALCHEMIST — Semantic Prompt Compiler Test Suite")
    run_scenario("Scenario A: 500-word Marketing Brief", SCENARIO_A)
    run_scenario("Scenario B: Complex Coding Instruction Set", SCENARIO_B)


if __name__ == "__main__":
    main()
