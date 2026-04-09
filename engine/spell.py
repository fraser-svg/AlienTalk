"""Spell correction layer for AlienTalk compression pipeline.

Uses SymSpell for O(1) lookup spell correction. Runs BEFORE dialect mapping
to avoid corrupting multi-word phrase matches in DIALECT_MAP.

Protected regions (code blocks, URLs, variable names) are skipped.
A tech-word allowlist prevents mangling of domain-specific terms.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from symspellpy import SymSpell, Verbosity


# ---------------------------------------------------------------------------
# Tech-word allowlist
# Terms added to the SymSpell dictionary as known-correct so they survive
# spell correction unchanged. ~500 terms covering DevOps, ML, web, cloud, etc.
# ---------------------------------------------------------------------------

TECH_ALLOWLIST: frozenset[str] = frozenset({
    # Container / orchestration
    "kubectl", "kubernetes", "k8s", "docker", "dockerfile", "podman",
    "containerd", "minikube", "k3s", "k3d", "kustomize", "istio",
    "envoy", "linkerd", "traefik", "ingress", "daemonset", "statefulset",
    "replicaset", "configmap", "etcd", "kubelet", "kubeadm", "kubeconfig",
    "cronjob", "sidecar", "nodeport",

    # Cloud / infra
    "terraform", "ansible", "pulumi", "cloudformation", "fargate",
    "lambda", "ec2", "s3", "rds", "ecs", "eks", "aks", "gke",
    "vpc", "cidr", "subnet", "nat", "alb", "elb", "nlb",
    "cloudflare", "cloudfront", "cdn", "dns", "cname", "arecord",
    "autoscaling", "autoscaler", "hpa", "vpa", "iam", "rbac",
    "datadog", "grafana", "prometheus", "loki", "jaeger", "zipkin",
    "pagerduty", "opsgenie", "nagios", "zabbix", "elasticsearch",
    "opensearch", "logstash", "kibana", "fluentd", "fluentbit",

    # CI/CD
    "github", "gitlab", "bitbucket", "jenkins", "circleci", "travisci",
    "buildkite", "argocd", "fluxcd", "tekton", "spinnaker",
    "codecov", "coveralls", "sonarqube", "snyk", "dependabot",

    # Web / frontend
    "webpack", "vite", "rollup", "esbuild", "parcel", "turbopack",
    "nextjs", "nuxtjs", "gatsby", "remix", "astro", "svelte",
    "sveltekit", "vuejs", "reactjs", "preact", "solidjs", "qwik",
    "tailwind", "tailwindcss", "postcss", "scss", "sass", "less",
    "storybook", "chromatic", "cypress", "playwright", "puppeteer",
    "vitest", "jest", "mocha", "chai", "sinon", "testcafe",
    "eslint", "prettier", "biome", "oxlint", "stylelint",
    "pnpm", "npm", "npx", "yarn", "bun", "deno", "nodejs",
    "tsx", "jsx", "mdx", "prisma", "drizzle", "sequelize",
    "typeorm", "knex", "graphql", "trpc", "grpc", "protobuf",
    "websocket", "webrtc", "wasm", "webassembly", "pwa",

    # Python
    "pytest", "mypy", "pyright", "ruff", "flake8", "pylint",
    "bandit", "isort", "autopep8", "yapf", "pipenv", "pyenv",
    "conda", "mamba", "virtualenv", "venv", "setuptools", "poetry",
    "pdm", "hatch", "uvicorn", "gunicorn", "hypercorn", "starlette",
    "fastapi", "django", "flask", "celery", "dramatiq", "huey",
    "sqlalchemy", "alembic", "pydantic", "marshmallow", "attrs",
    "dataclasses", "asyncio", "aiohttp", "httpx", "urllib",
    "beautifulsoup", "scrapy", "lxml", "jinja", "mako",
    "numpy", "scipy", "pandas", "polars", "dask", "vaex",
    "matplotlib", "seaborn", "plotly", "bokeh", "altair",
    "cython", "numba", "pypy", "cpython", "ipython", "jupyter",
    "nbconvert", "jupyterlab", "ipywidgets", "streamlit", "gradio",

    # ML / AI
    "pytorch", "tensorflow", "keras", "jax", "flax", "optax",
    "sklearn", "scikit", "xgboost", "lightgbm", "catboost",
    "huggingface", "transformers", "tokenizers", "datasets",
    "langchain", "llamaindex", "llama", "llm", "llms",
    "openai", "anthropic", "claude", "chatgpt", "gemini", "gpt",
    "cuda", "cudnn", "tensorrt", "onnx", "mlflow", "wandb",
    "comet", "neptune", "optuna", "hyperopt", "raytune",
    "faiss", "annoy", "milvus", "pinecone", "weaviate", "qdrant",
    "chromadb", "pgvector", "embeddings", "finetune", "finetuning",
    "lora", "qlora", "peft", "rlhf", "dpo", "sft",
    "vllm", "tgi", "triton", "deepspeed", "megatron",
    "diffusers", "stablediffusion", "dalle", "midjourney",
    "tokenizer", "tokenization", "detokenize", "bpe",
    "automl", "autoencoder", "variational", "gan", "vae",
    "bert", "roberta", "deberta", "electra", "albert",
    "resnet", "efficientnet", "mobilenet", "yolo", "detr",
    "rag", "mcp", "agentic",

    # Rust
    "cargo", "rustc", "rustup", "rustfmt", "clippy", "tokio",
    "actix", "axum", "hyper", "reqwest", "serde", "rayon",
    "crossbeam", "parking", "tracing", "anyhow", "thiserror",
    "clap", "structopt", "pyo3", "maturin", "warp", "tonic",
    "tauri", "egui", "iced", "bevy", "wgpu", "napi",

    # Go
    "goroutine", "goroutines", "gomod", "gosum", "gofmt",
    "golint", "govet", "govulncheck", "cobra", "viper", "gin",
    "echo", "fiber", "chi", "mux", "gorm", "sqlx", "pgx",

    # Database
    "postgres", "postgresql", "mysql", "mariadb", "sqlite",
    "mongodb", "dynamodb", "cassandra", "scylladb", "cockroachdb",
    "couchdb", "couchbase", "firestore", "supabase", "neon",
    "planetscale", "turso", "redis", "memcached", "valkey",
    "clickhouse", "timescaledb", "influxdb", "questdb",
    "neo4j", "arangodb", "dgraph", "edgedb",
    "flyway", "liquibase",

    # DevOps / tools
    "nginx", "apache", "caddy", "haproxy", "envoy",
    "systemd", "systemctl", "journalctl", "supervisord",
    "tmux", "zsh", "bash", "fish", "nushell", "powershell",
    "homebrew", "brew", "apt", "yum", "dnf", "pacman", "snap",
    "nix", "nixos", "flake", "devcontainer", "codespace",
    "vagrant", "packer", "consul", "vault", "nomad",
    "wireguard", "tailscale", "zerotier", "mosh", "ssh",
    "rsync", "scp", "curl", "wget", "httpie", "grpcurl",
    "jq", "yq", "fzf", "ripgrep", "fd", "bat", "exa", "zoxide",
    "starship", "neovim", "nvim", "vim", "emacs", "helix",
    "lazygit", "lazydocker", "gh", "glab",

    # macOS / Apple
    "xcode", "xcrun", "xctest", "swiftui", "uikit", "appkit",
    "coredata", "corebluetooth", "coreml", "arkit", "realitykit",
    "visionos", "watchos", "tvos", "macos", "ios", "ipados",
    "cocoapods", "carthage", "spm", "tuist", "fastlane",
    "notarize", "codesign", "entitlements", "provisioning",
    "keychain", "accessibility",

    # Networking / protocols
    "http", "https", "tcp", "udp", "quic", "mqtt", "amqp",
    "nats", "kafka", "rabbitmq", "pulsar", "kinesis", "sqs",
    "sns", "pubsub", "eventbridge", "webhook", "oauth",
    "oidc", "saml", "jwt", "hmac", "cors", "csrf", "xss",
    "owasp", "cve", "tls", "ssl", "mtls", "acme",
    "letsencrypt", "certbot",

    # Formats / standards
    "json", "yaml", "toml", "xml", "csv", "parquet", "avro",
    "msgpack", "cbor", "bson", "jsonl", "ndjson", "jsonpath",
    "jmespath", "xpath", "regex", "regexp", "glob", "semver",
    "openapi", "swagger", "asyncapi", "jsonschema",

    # Misc tech terms commonly misspelled
    "localhost", "stderr", "stdout", "stdin",
    "middleware", "microservice", "microservices", "monorepo",
    "monolith", "serverless", "jamstack", "headless",
    "idempotent", "idempotency", "immutable", "mutable",
    "serialization", "deserialization", "marshalling",
    "refactor", "refactoring", "linting", "linter",
    "transpile", "transpiler", "polyfill", "shim",
    "debounce", "throttle", "memoize", "memoization",
    "mutex", "semaphore", "deadlock", "livelock", "spinlock",
    "coroutine", "subroutine", "subprocess", "multiprocessing",
    "multithreading", "concurrency", "parallelism",
    "upsert", "dedup", "deduplicate", "deduplication",
    "backpressure", "backoff", "retryable", "idempotent",
    "sharding", "partitioning", "replication", "failover",
    "canary", "bluegreen", "rollback", "hotfix",
    "dockerfile", "makefile", "rakefile", "procfile",
    "gitignore", "dockerignore", "eslintrc", "prettierrc",
    "tsconfig", "webpack", "viteconfig", "turbo",
    "symspell", "symlink", "hardlink", "inode",
    "crontab", "cronjob", "systemd", "launchd",
    "api", "apis", "sdk", "cli", "gui", "tui", "repl",
    "crud", "orm", "odm", "dao", "dto", "ddd",
    "ci", "cd", "sre", "sla", "slo", "sli",
    "cpu", "gpu", "tpu", "fpga", "asic",
    "ascii", "utf8", "unicode", "base64",
    "enum", "struct", "tuple", "hashmap", "treemap",
    "btree", "trie", "heap", "deque", "bitset",
    "args", "kwargs", "params", "config", "env",
    "async", "await", "callback", "promise", "observable",
})

# Max edit distance for SymSpell suggestions
_MAX_EDIT_DISTANCE = 2

# Patterns to skip during spell correction
_URL_RE = re.compile(
    r'https?://\S+|'
    r'www\.\S+|'
    r'\S+\.\w{2,4}/\S*'
)
_EMAIL_RE = re.compile(r'\S+@\S+\.\S+')
_VARIABLE_RE = re.compile(
    r'(?:'
    r'[a-z]+[A-Z]\w*|'          # camelCase
    r'[A-Z][a-z]+[A-Z]\w*|'     # PascalCase with mixed
    r'\w+_\w+|'                  # snake_case
    r'[A-Z]{2,}(?:_[A-Z]+)*|'   # SCREAMING_SNAKE
    r'\$\w+|'                    # $variables
    r'@\w+|'                     # @decorators / @mentions
    r'#\w+|'                     # #hashtags / #channels
    r'--[\w-]+|'                 # CLI flags --flag-name
    r'-[a-zA-Z]\b'               # Short flags -v
    r')'
)
_PATH_RE = re.compile(r'[~/.][\w./\\-]+')
_CODE_SENTINEL_RE = re.compile(r'\x00CODE_BLOCK_\d+\x00')


class SpellCorrector:
    """SymSpell-based spell corrector with tech-word awareness."""

    def __init__(self, max_edit_distance: int = _MAX_EDIT_DISTANCE) -> None:
        self._sym = SymSpell(max_dictionary_edit_distance=max_edit_distance)
        self._max_edit_distance = max_edit_distance
        self._loaded = False
        self._load_dictionaries()

    def _load_dictionaries(self) -> None:
        """Load English frequency dictionary + tech allowlist."""
        # SymSpell ships with an English frequency dictionary
        dict_path = os.path.join(
            os.path.dirname(__file__),
            "..",  # walk up from engine/
        )
        # Use the bundled dictionary from symspellpy package
        import symspellpy as _pkg
        pkg_dir = os.path.dirname(_pkg.__file__)
        freq_dict = os.path.join(pkg_dir, "frequency_dictionary_en_82_765.txt")

        if os.path.exists(freq_dict):
            self._sym.load_dictionary(
                freq_dict,
                term_index=0,
                count_index=1,
            )

        # Add tech allowlist words with high frequency so they're never "corrected"
        for term in TECH_ALLOWLIST:
            self._sym.create_dictionary_entry(term, 1_000_000)

        # Boost prompt-domain words that SymSpell might otherwise lose to
        # higher-frequency alternatives (e.g., "analyze" losing to "realize")
        _PROMPT_DOMAIN_BOOSTS = [
            "analyze", "summarize", "explain", "generate", "implement",
            "classify", "evaluate", "extract", "translate", "rewrite",
            "refactor", "optimize", "compare", "contrast", "describe",
            "elaborate", "enumerate", "prioritize", "categorize",
            "paraphrase", "synthesize", "contextualize", "visualize",
        ]
        for term in _PROMPT_DOMAIN_BOOSTS:
            self._sym.create_dictionary_entry(term, 5_000_000)

        self._loaded = True

    def _should_skip(self, word: str) -> bool:
        """Return True if this word should not be spell-checked."""
        # Code sentinels
        if _CODE_SENTINEL_RE.match(word):
            return True
        # URLs, emails, paths
        if _URL_RE.match(word):
            return True
        if _EMAIL_RE.match(word):
            return True
        if _PATH_RE.match(word):
            return True
        # Variable names (camelCase, snake_case, etc.)
        if _VARIABLE_RE.match(word):
            return True
        # Words with digits mixed in (version numbers, hashes, etc.)
        if re.search(r'\d', word):
            return True
        # Already in tech allowlist (case-insensitive)
        if word.lower() in TECH_ALLOWLIST:
            return True
        # Single characters
        if len(word) <= 1:
            return True
        # All caps (acronyms)
        stripped = re.sub(r'[^a-zA-Z]', '', word)
        if stripped.isupper() and len(stripped) >= 2:
            return True
        return False

    def correct_word(self, word: str) -> str:
        """Correct a single word. Returns original if no good suggestion."""
        # Check the full original word before stripping punctuation,
        # so "pyo3" hits the allowlist/digit check before "3" is stripped
        if self._should_skip(word):
            return word

        # Strip trailing punctuation for lookup, preserve it
        trailing = ""
        leading = ""
        while word and not word[-1].isalpha():
            trailing = word[-1] + trailing
            word = word[:-1]
        while word and not word[0].isalpha():
            leading += word[0]
            word = word[1:]

        if not word:
            return leading + trailing

        if self._should_skip(word):
            return leading + word + trailing

        # Preserve original casing pattern
        was_title = word[0].isupper() and (len(word) == 1 or word[1:].islower())
        was_upper = word.isupper()

        suggestions = self._sym.lookup(
            word.lower(),
            Verbosity.CLOSEST,
            max_edit_distance=self._max_edit_distance,
        )

        if not suggestions:
            return leading + word + trailing

        best = suggestions[0]

        # Only accept if edit distance is reasonable relative to word length
        if best.distance == 0:
            return leading + word + trailing  # Already correct

        # For short words (<=4 chars), only accept distance 1
        if len(word) <= 4 and best.distance > 1:
            return leading + word + trailing

        corrected = best.term

        # Restore casing
        if was_upper:
            corrected = corrected.upper()
        elif was_title:
            corrected = corrected.capitalize()

        return leading + corrected + trailing

    def correct_text(self, text: str) -> str:
        """Correct spelling in text, skipping protected regions.

        Expects code blocks to already be extracted (replaced with sentinels).
        """
        if not self._loaded:
            return text

        # Split on whitespace but preserve the whitespace
        parts = re.split(r'(\s+)', text)
        corrected_parts: list[str] = []

        for part in parts:
            if not part or part.isspace():
                corrected_parts.append(part)
            else:
                corrected_parts.append(self.correct_word(part))

        return ''.join(corrected_parts)


# Module-level singleton (lazy init)
_corrector: SpellCorrector | None = None


def get_corrector() -> SpellCorrector:
    """Get or create the module-level SpellCorrector singleton."""
    global _corrector
    if _corrector is None:
        _corrector = SpellCorrector()
    return _corrector


def correct_spelling(text: str) -> str:
    """Convenience function: correct spelling in text."""
    return get_corrector().correct_text(text)
