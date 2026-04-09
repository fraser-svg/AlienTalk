//! Stage 2: Compress — machine-facing, invisible to user.
//!
//! Pipeline: symbols → strip → minify
//! Produces token-dense output that LLMs understand but humans can't read.

pub mod minify;
pub mod strip;
pub mod symbols;

use crate::safety;
use symbols::{escape_literal_symbols, stage_symbols, unescape_literal_symbols};
use strip::stage_strip;
use minify::stage_minify;

/// Result from Stage 2 compression.
#[derive(Debug, Clone)]
pub struct CompressResult {
    pub compressed_text: String,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub saved_tokens: u64,
    pub percentage_saved: f64,
}

/// Approximate token count (whitespace split).
fn count_tokens(text: &str) -> u64 {
    text.split_whitespace().count() as u64
}

/// Run Stage 2 compression pipeline.
///
/// Takes already-sharpened text (or raw text) and produces machine-optimised output.
/// Skips processing for prompts under 15 words.
pub fn compress(text: &str) -> CompressResult {
    let input_tokens = count_tokens(text);

    // Short prompt pass-through (spec: prompts under 15 words skip Stage 2)
    if safety::is_short_prompt(text) {
        return CompressResult {
            compressed_text: text.to_string(),
            input_tokens,
            output_tokens: input_tokens,
            saved_tokens: 0,
            percentage_saved: 0.0,
        };
    }

    compress_unchecked(text)
}

/// Run Stage 2 compression without the short-prompt guard.
///
/// Used by the legacy `compile()` function for backward compatibility.
pub fn compress_unchecked(text: &str) -> CompressResult {
    let input_tokens = count_tokens(text);

    // Pre-process: escape literal symbols in user text
    let work = escape_literal_symbols(text);

    // Extract code blocks to protect from compression
    let (work, fenced_blocks) = safety::extract_code_blocks(&work);
    let (work, inline_blocks) = safety::detect_inline_code(&work);
    let mut all_blocks = fenced_blocks;
    all_blocks.extend(inline_blocks);

    // Compute logic density → adjust compression intensity
    let logic_density = safety::compute_logic_density(text);
    let intensity = safety::intensity_from_density(logic_density);

    // Three-stage compression pipeline
    let work = stage_symbols(&work, intensity);
    let work = stage_strip(&work, intensity);
    let work = stage_minify(&work, intensity);

    // Post-process: restore code blocks and literal symbols
    let work = safety::restore_blocks(&work, &all_blocks);
    let compressed_text = unescape_literal_symbols(&work);

    let output_tokens = count_tokens(&compressed_text);
    let saved_tokens = input_tokens.saturating_sub(output_tokens);

    CompressResult {
        compressed_text,
        input_tokens,
        output_tokens,
        saved_tokens,
        percentage_saved: if input_tokens > 0 {
            ((saved_tokens as f64 / input_tokens as f64) * 1000.0).round() / 10.0
        } else {
            0.0
        },
    }
}

/// Reverse symbolic mapping for human readability (approximate).
pub fn decompile(compressed: &str) -> String {
    symbols::decompile(compressed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compress_empty() {
        let r = compress("");
        assert_eq!(r.compressed_text, "");
    }

    #[test]
    fn compress_preserves_code_blocks() {
        let input = "Fix this code and explain step by step:\n```python\ndef hello():\n    pass\n```\nMake it better and more concise";
        let r = compress(input);
        assert!(r.compressed_text.contains("```python"));
        assert!(r.compressed_text.contains("def hello()"));
    }

    #[test]
    fn compress_applies_symbols() {
        let input = "I want you to explain step by step how databases work and summarize the key findings";
        let r = compress(input);
        assert!(r.compressed_text.contains("CoT"));
        assert!(r.compressed_text.contains("Σ"));
    }

    #[test]
    fn compress_negation_aware() {
        let input = "Do not act as a therapist in this conversation and do not pretend you are something else";
        let r = compress(input);
        assert!(!r.compressed_text.contains("@role:"));
    }

    #[test]
    fn compress_returns_stats() {
        let input = "I want you to explain how databases work and provide a detailed explanation of the concepts";
        let r = compress(input);
        assert!(r.saved_tokens > 0);
        assert!(r.percentage_saved > 0.0);
    }

    #[test]
    fn short_prompt_passthrough() {
        let input = "Hello world";
        let r = compress(input);
        assert_eq!(r.compressed_text, input);
        assert_eq!(r.saved_tokens, 0);
    }
}
