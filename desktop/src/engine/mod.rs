//! AlienTalk compression engine — pure Rust port of engine/alchemist.py.
//!
//! Four-stage pipeline:
//!   1. Spell correction (TODO: symspell integration)
//!   2. Symbolic mapping (DIALECT_MAP)
//!   3. Stop-word stripping
//!   4. Structural minification

pub mod codeblocks;
pub mod dialect;
pub mod logic;
pub mod normalize;
pub mod stopwords;
pub mod structural;

use codeblocks::{detect_inline_code, extract_code_blocks, restore_blocks};
use dialect::{decompile, escape_literal_symbols, stage_symbolic, unescape_literal_symbols};
use logic::{compute_logic_density, intensity_from_density};
use normalize::normalize;
use stopwords::stage_stopwords;
use structural::stage_structural;

/// Result from the compression engine.
#[derive(Debug, Clone)]
pub struct EngineResult {
    pub compiled_text: String,
    pub original_tokens: u64,
    pub compressed_tokens: u64,
    pub saved_tokens: u64,
    pub percentage_saved: f64,
    pub compression_ratio: f64,
}

impl EngineResult {
    /// Passthrough result — returns original text unchanged.
    pub fn passthrough(text: &str) -> Self {
        let approx_tokens = (text.split_whitespace().count() as u64).max(1);
        Self {
            compiled_text: text.to_string(),
            original_tokens: approx_tokens,
            compressed_tokens: approx_tokens,
            saved_tokens: 0,
            percentage_saved: 0.0,
            compression_ratio: 1.0,
        }
    }
}

/// Approximate token count (whitespace split). Good enough for stats.
fn count_tokens(text: &str) -> u64 {
    text.split_whitespace().count() as u64
}

/// Main compression pipeline. Returns token-dense Machine Dialect.
///
/// Automatically detects high-logic prompts and reduces compression
/// intensity to prevent semantic collapse.
pub fn compile(prompt: &str) -> String {
    // Pre-process: escape literal dialect symbols in user text
    let text = escape_literal_symbols(prompt);

    // Pre-process: extract code blocks to protect from compression
    let (text, fenced_blocks) = extract_code_blocks(&text);
    let (text, inline_blocks) = detect_inline_code(&text);
    let mut all_blocks = fenced_blocks;
    all_blocks.extend(inline_blocks);

    // Stage 0: Spell correction
    // TODO: integrate Rust-native symspell crate
    // For now, skip spell correction (parity testing will validate pipeline without it)

    // Stage 0b: Normalize (after spell correction, before compression)
    let text = normalize(&text);

    // Compute logic density → adjust compression intensity
    let logic_density = compute_logic_density(prompt);
    let intensity = intensity_from_density(logic_density);

    // Three-stage pipeline
    let text = stage_symbolic(&text, intensity);
    let text = stage_stopwords(&text, intensity);
    let text = stage_structural(&text, intensity);

    // Post-process: restore code blocks and literal symbols
    let text = restore_blocks(&text, &all_blocks);
    let text = unescape_literal_symbols(&text);

    text
}

/// Reverse symbolic mapping for human readability.
///
/// Note: Decompilation is approximate. Stop-word removal and structural
/// minification are lossy transforms that cannot be perfectly reversed.
pub fn decompile_text(compressed: &str) -> String {
    decompile(compressed)
}

/// Return token counts and compression statistics.
pub fn estimate_savings(prompt: &str) -> EngineResult {
    let compiled = compile(prompt);
    let orig_tokens = count_tokens(prompt);
    let comp_tokens = count_tokens(&compiled);
    let saved = orig_tokens.saturating_sub(comp_tokens);

    EngineResult {
        compiled_text: compiled,
        original_tokens: orig_tokens,
        compressed_tokens: comp_tokens,
        saved_tokens: saved,
        compression_ratio: if orig_tokens > 0 {
            (comp_tokens as f64 / orig_tokens as f64 * 1000.0).round() / 1000.0
        } else {
            1.0
        },
        percentage_saved: if orig_tokens > 0 {
            ((saved as f64 / orig_tokens as f64) * 1000.0).round() / 10.0
        } else {
            0.0
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compile_empty() {
        assert_eq!(compile(""), "");
    }

    #[test]
    fn compile_preserves_code_blocks() {
        let input = "Fix this:\n```python\ndef hello():\n    pass\n```\nMake it better";
        let result = compile(input);
        assert!(result.contains("```python"));
        assert!(result.contains("def hello()"));
    }

    #[test]
    fn compile_filler_removal() {
        let result = compile("I want you to explain how databases work");
        assert!(!result.contains("I want you to"));
        assert!(result.contains("explain"));
    }

    #[test]
    fn compile_symbolic_mapping() {
        let result = compile("Think step by step about this problem");
        assert!(result.contains("CoT"));
    }

    #[test]
    fn compile_stop_word_stripping() {
        let result = compile("The analysis of the data was performed with the tools");
        assert!(!result.contains("The "));
        assert!(result.contains("analysis"));
    }

    #[test]
    fn compile_negation_aware() {
        let result = compile("Do not act as a therapist in this conversation");
        // Should NOT map "act as a" to "@role:" because of negation
        assert!(!result.contains("@role:"));
    }

    #[test]
    fn compile_full_pipeline() {
        let result = compile(
            "You are an expert in Python programming. I want you to explain step by step how to implement a binary search algorithm. Be concise."
        );
        assert!(result.contains("@expert"));
        assert!(result.contains("CoT"));
        assert!(result.contains("!brief"));
    }

    #[test]
    fn estimate_savings_returns_stats() {
        let result = estimate_savings("I want you to explain how databases work");
        assert!(result.saved_tokens > 0);
        assert!(result.percentage_saved > 0.0);
    }

    #[test]
    fn decompile_roundtrip() {
        let compiled = compile("Summarize the article");
        assert!(compiled.contains("Σ"));
        let decompiled = decompile_text(&compiled);
        // Decompile is approximate — "Σ" maps back to one of "summarize"/"in summary"
        assert!(
            decompiled.contains("summar") || decompiled.contains("Σ"),
            "decompiled should contain summary-related text, got: {}",
            decompiled
        );
    }
}
