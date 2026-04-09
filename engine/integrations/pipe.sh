#!/bin/bash
# Alchemist CLI Pipe — preprocess prompts before passing to any LLM CLI.
#
# Usage:
#   # One-shot:
#   echo "Your verbose prompt" | ./integrations/pipe.sh | claude
#
#   # Add as shell alias for always-on:
#   alias ask='f(){ echo "$*" | python3 /path/to/alchemist.py --prompt "$(cat)" --no-stats; }; f'
#
#   # Then just:
#   ask "You are an expert. Summarize this report. Format as a table."
#
#   # Or pipe a file:
#   cat prompt.txt | ./integrations/pipe.sh
#
# Install as alias (add to ~/.zshrc or ~/.bashrc):
#
#   export ALIENTALK_HOME="/path/to/alientalk/engine"
#   alias alc='python3 $ALIENTALK_HOME/alchemist.py --prompt'
#   alias alcp='python3 $ALIENTALK_HOME/alchemist_prime.py --prompt'

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -t 0 ]; then
    # No stdin — use args
    INPUT="$*"
else
    # Read from stdin
    INPUT="$(cat)"
fi

if [ -z "$INPUT" ]; then
    echo "Usage: echo 'prompt' | pipe.sh" >&2
    echo "   or: pipe.sh 'your prompt here'" >&2
    exit 1
fi

python3 "$SCRIPT_DIR/alchemist.py" --prompt "$INPUT" --no-stats
