//! Stage 1: Sharpen — user-facing, human-readable prompt improvement.
//!
//! Pipeline: filler removal → rewrite → cleanup
//! Produces a clean, specific, well-structured prompt the user can read and approve.

pub mod cleanup;
pub mod filler;
pub mod rewrite;

use crate::safety;

/// Result from Stage 1 sharpening.
#[derive(Debug, Clone)]
pub struct SharpenResult {
    pub sharpened_text: String,
    pub original_tokens: u64,
    pub sharpened_tokens: u64,
    pub saved_tokens: u64,
    pub percentage_saved: f64,
}

/// Approximate token count (whitespace split).
fn count_tokens(text: &str) -> u64 {
    text.split_whitespace().count() as u64
}

/// Run Stage 1 sharpening pipeline.
///
/// Produces human-readable improved text. The user sees this and approves it.
/// Skips processing for prompts under 15 words.
pub fn sharpen(text: &str) -> SharpenResult {
    let original_tokens = count_tokens(text);

    // Short prompt pass-through
    if safety::is_short_prompt(text) {
        return SharpenResult {
            sharpened_text: text.to_string(),
            original_tokens,
            sharpened_tokens: original_tokens,
            saved_tokens: 0,
            percentage_saved: 0.0,
        };
    }

    // Extract code blocks and [keep:] blocks to protect from processing
    let (work, code_blocks) = safety::extract_code_blocks(text);
    let (work, inline_blocks) = safety::detect_inline_code(&work);
    let (work, keep_blocks) = safety::extract_keep_blocks(&work);
    let mut all_blocks = code_blocks;
    all_blocks.extend(inline_blocks);
    all_blocks.extend(keep_blocks);

    // Stage 1 pipeline: filler → rewrite → cleanup
    let work = filler::remove_filler(&work);
    let work = rewrite::rewrite(&work);
    let work = cleanup::cleanup(&work);

    // Restore protected blocks
    let sharpened_text = safety::restore_blocks(&work, &all_blocks);

    let sharpened_tokens = count_tokens(&sharpened_text);
    let saved_tokens = original_tokens.saturating_sub(sharpened_tokens);

    SharpenResult {
        sharpened_text,
        original_tokens,
        sharpened_tokens,
        saved_tokens,
        percentage_saved: if original_tokens > 0 {
            ((saved_tokens as f64 / original_tokens as f64) * 1000.0).round() / 10.0
        } else {
            0.0
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sharpen_removes_filler_and_rewrites() {
        let result = sharpen(
            "Hey, I was wondering if you could help me out with something. I need you to \
             take this list of customer names and email addresses and turn it into a nicely \
             formatted JSON object. Each customer should have a name field and an email field. \
             Please make sure the JSON is valid and properly indented. Thank you so much!"
        );
        // Should remove: "Hey", "I was wondering if you could", "Thank you so much"
        assert!(!result.sharpened_text.contains("wondering"));
        assert!(!result.sharpened_text.contains("Thank you"));
        // Should keep meaningful content
        assert!(result.sharpened_text.contains("JSON"));
        assert!(result.sharpened_text.contains("name"));
        assert!(result.sharpened_text.contains("email"));
        // Should save tokens
        assert!(result.saved_tokens > 0);
        assert!(result.percentage_saved > 0.0);
    }

    #[test]
    fn sharpen_protects_code() {
        let input = "I was wondering if you could fix this code: `let x = 42;` and make it work with the function. I would also like you to add error handling to the overall implementation.";
        let result = sharpen(input);
        assert!(result.sharpened_text.contains("`let x = 42;`"));
    }

    #[test]
    fn sharpen_short_passthrough() {
        let input = "Sort this list";
        let result = sharpen(input);
        assert_eq!(result.sharpened_text, input);
        assert_eq!(result.saved_tokens, 0);
    }

    #[test]
    fn sharpen_empty() {
        let result = sharpen("");
        assert_eq!(result.sharpened_text, "");
    }

    #[test]
    fn sharpen_protects_keep_blocks() {
        let input = "I was wondering if you could rewrite this but [keep: exactly this wording] should stay the same in the final version of the document";
        let result = sharpen(input);
        assert!(result.sharpened_text.contains("exactly this wording"));
    }
}
