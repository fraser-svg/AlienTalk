//! Sharp prompt optimization engine.
//!
//! Two-stage pipeline:
//!   Stage 1 (Sharpen): Human-readable improvement — filler removal, rewriting, cleanup
//!   Stage 2 (Compress): Machine-facing compression — symbols, stripping, minification
//!
//! Public API:
//!   `sharpen(text)` — Stage 1 only (user sees result)
//!   `compress(text)` — Stage 2 only (model receives result)
//!   `process(text)`  — Both stages combined

pub mod safety;
pub mod scorer;
pub mod stage1;
pub mod stage2;

#[cfg(target_arch = "wasm32")]
use wasm_bindgen::prelude::*;

// Re-export result types
pub use scorer::QualityScore;
pub use stage1::SharpenResult;
pub use stage2::CompressResult;

/// Result from the full two-stage pipeline.
#[derive(Debug, Clone)]
pub struct ProcessResult {
    /// Stage 1 output (human-readable).
    pub sharpened_text: String,
    /// Stage 2 output (machine-optimised).
    pub compressed_text: String,
    /// Quality score before processing.
    pub score_before: QualityScore,
    /// Quality score after Stage 1.
    pub score_after: QualityScore,
    /// Original token count.
    pub original_tokens: u64,
    /// Tokens after Stage 1.
    pub sharpened_tokens: u64,
    /// Tokens after Stage 2.
    pub compressed_tokens: u64,
    /// Total tokens saved (original - compressed).
    pub total_saved: u64,
    /// Total percentage saved.
    pub total_percentage_saved: f64,
}

/// Stage 1: Sharpen a prompt for human readability.
///
/// Removes filler, rewrites verbose constructions, cleans up structure.
/// The user sees this result and approves it (or undoes it).
pub fn sharpen(text: &str) -> SharpenResult {
    stage1::sharpen(text)
}

/// Stage 2: Compress a prompt for machine consumption.
///
/// Applies symbol replacement, stop-word stripping, JSON minification.
/// The user never sees this — it's applied to the outbound API request.
pub fn compress(text: &str) -> CompressResult {
    stage2::compress(text)
}

/// Run both stages: sharpen then compress.
///
/// Returns the full pipeline result with before/after scores.
pub fn process(text: &str) -> ProcessResult {
    let score_before = scorer::score(text);
    let stage1_result = sharpen(text);
    let score_after = scorer::score(&stage1_result.sharpened_text);
    let stage2_result = compress(&stage1_result.sharpened_text);

    let total_saved = stage1_result.original_tokens.saturating_sub(stage2_result.output_tokens);

    ProcessResult {
        sharpened_text: stage1_result.sharpened_text,
        compressed_text: stage2_result.compressed_text,
        score_before,
        score_after,
        original_tokens: stage1_result.original_tokens,
        sharpened_tokens: stage1_result.sharpened_tokens,
        compressed_tokens: stage2_result.output_tokens,
        total_saved,
        total_percentage_saved: if stage1_result.original_tokens > 0 {
            ((total_saved as f64 / stage1_result.original_tokens as f64) * 1000.0).round() / 10.0
        } else {
            0.0
        },
    }
}

/// Reverse Stage 2 symbolic mapping (approximate).
pub fn decompile(compressed: &str) -> String {
    stage2::decompile(compressed)
}

// ---------------------------------------------------------------------------
// Legacy compat: compile() maps to compress() for existing tests/desktop
// ---------------------------------------------------------------------------

/// Legacy: single-stage compression (maps to Stage 2 compress).
///
/// Kept for backward compatibility with desktop app and golden parity tests.
/// Runs cleanup (punctuation normalization) then compression, bypassing
/// the short-prompt guard (original engine had no such guard).
pub fn compile(text: &str) -> String {
    let cleaned = stage1::cleanup::normalize_punctuation(text);
    let result = stage2::compress_unchecked(&cleaned);
    result.compressed_text
}

/// Legacy: estimate savings (maps to Stage 2 compress).
pub fn estimate_savings(text: &str) -> LegacyEngineResult {
    let result = stage2::compress_unchecked(text);
    LegacyEngineResult {
        compiled_text: result.compressed_text,
        original_tokens: result.input_tokens,
        compressed_tokens: result.output_tokens,
        saved_tokens: result.saved_tokens,
        percentage_saved: result.percentage_saved,
        compression_ratio: if result.input_tokens > 0 {
            (result.output_tokens as f64 / result.input_tokens as f64 * 1000.0).round() / 1000.0
        } else {
            1.0
        },
    }
}

/// Legacy result type for backward compatibility.
#[derive(Debug, Clone)]
pub struct LegacyEngineResult {
    pub compiled_text: String,
    pub original_tokens: u64,
    pub compressed_tokens: u64,
    pub saved_tokens: u64,
    pub percentage_saved: f64,
    pub compression_ratio: f64,
}

impl LegacyEngineResult {
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

// ---------------------------------------------------------------------------
// WASM bindings
// ---------------------------------------------------------------------------

#[cfg(target_arch = "wasm32")]
#[wasm_bindgen]
pub fn wasm_sharpen(text: &str) -> String {
    let result = sharpen(text);
    result.sharpened_text
}

#[cfg(target_arch = "wasm32")]
#[wasm_bindgen]
pub fn wasm_compress(text: &str) -> String {
    let result = compress(text);
    result.compressed_text
}

#[cfg(target_arch = "wasm32")]
#[wasm_bindgen]
pub fn wasm_score(text: &str) -> u32 {
    scorer::score(text).total
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
        let decompiled = decompile(&compiled);
        assert!(
            decompiled.contains("summar") || decompiled.contains("Σ"),
            "decompiled should contain summary-related text, got: {}",
            decompiled
        );
    }

    #[test]
    fn process_runs_both_stages() {
        let result = process(
            "Hey, I was wondering if you could help me out with something important. I need you to \
             explain step by step how relational databases work, including indexing strategies and \
             query optimization techniques. Please make sure to be concise and thorough. Thank you so much!"
        );
        // Stage 1 should remove filler
        assert!(!result.sharpened_text.contains("wondering"));
        // Stage 2 should compress
        assert!(result.compressed_text.len() < result.sharpened_text.len());
        // Scores should improve
        assert!(result.score_after.total >= result.score_before.total);
        // Tokens should decrease
        assert!(result.total_saved > 0);
    }

    #[test]
    fn sharpen_produces_readable_output() {
        let result = sharpen(
            "I was wondering if you could help me out. In order to fix this bug, I need you to \
             take into consideration the error log and make changes to the authentication module."
        );
        // Should be readable and concise
        assert!(!result.sharpened_text.contains("wondering"));
        assert!(!result.sharpened_text.contains("In order to"));
        assert!(result.sharpened_text.contains("fix"));
        assert!(result.sharpened_text.contains("authentication"));
    }
}
