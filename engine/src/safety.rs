//! Safety module — code block protection and logic density detection.
//!
//! Shared by both Stage 1 (sharpen) and Stage 2 (compress).
//! Ensures code, negation, logic, and protected content are never modified.

use std::collections::HashMap;
use std::sync::LazyLock;

use regex::Regex;

// ---------------------------------------------------------------------------
// Code block extraction (protects code from both stages)
// ---------------------------------------------------------------------------

const CODE_BLOCK_SENTINEL: &str = "\x00CODE_BLOCK_";
const CODE_BLOCK_SENTINEL_END: &str = "\x00";

static FENCED_CODE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)```[\s\S]*?```").unwrap());
static INLINE_CODE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`[^`]+`").unwrap());
static CODE_INDICATORS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)(?:def\s+\w+\s*\(|class\s+\w+[\s(:]|SELECT\s+.+?\s+FROM|import\s+\w|function\s+\w+\s*\(|(?:const|let|var)\s+\w+|(?:CREATE|DROP|ALTER|INSERT|UPDATE|DELETE)\s+)").unwrap()
});
static COLON_CODE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?im)((?:code|query|pattern|regex|command|script|sql|expression)\s*:\s*)(.*?)$")
        .unwrap()
});
static CODE_LIKE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[(){}\[\]<>=;|&^$\\]").unwrap());

/// Regex for `[keep: ...]` brackets — content inside is protected.
static KEEP_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[keep:\s*(.*?)\]").unwrap());

fn sentinel(n: usize) -> String {
    format!("{}{}{}", CODE_BLOCK_SENTINEL, n, CODE_BLOCK_SENTINEL_END)
}

/// Extract fenced and inline code blocks, replacing with sentinels.
pub fn extract_code_blocks(text: &str) -> (String, HashMap<String, String>) {
    let mut blocks = HashMap::new();
    let mut counter = 0usize;

    // Fenced code blocks first
    let mut result = FENCED_CODE_RE
        .replace_all(text, |caps: &regex::Captures| {
            let key = sentinel(counter);
            blocks.insert(key.clone(), caps[0].to_string());
            counter += 1;
            key
        })
        .into_owned();

    // Inline code
    result = INLINE_CODE_RE
        .replace_all(&result, |caps: &regex::Captures| {
            let key = sentinel(counter);
            blocks.insert(key.clone(), caps[0].to_string());
            counter += 1;
            key
        })
        .into_owned();

    (result, blocks)
}

/// Detect un-fenced code segments (after colon patterns).
pub fn detect_inline_code(text: &str) -> (String, HashMap<String, String>) {
    let mut blocks = HashMap::new();
    let mut counter = 1000usize;

    let result = COLON_CODE_RE
        .replace_all(text, |caps: &regex::Captures| {
            let prefix = &caps[1];
            let code_part = &caps[2];
            if CODE_INDICATORS.is_match(code_part) || CODE_LIKE_RE.is_match(code_part) {
                let key = sentinel(counter);
                blocks.insert(key.clone(), code_part.to_string());
                counter += 1;
                format!("{}{}", prefix, key)
            } else {
                caps[0].to_string()
            }
        })
        .into_owned();

    (result, blocks)
}

/// Extract `[keep: ...]` protected content, replacing with sentinels.
pub fn extract_keep_blocks(text: &str) -> (String, HashMap<String, String>) {
    let mut blocks = HashMap::new();
    let mut counter = 2000usize;

    let result = KEEP_RE
        .replace_all(text, |caps: &regex::Captures| {
            let key = sentinel(counter);
            blocks.insert(key.clone(), caps[1].to_string());
            counter += 1;
            key
        })
        .into_owned();

    (result, blocks)
}

/// Restore code blocks from sentinels.
pub fn restore_blocks(text: &str, blocks: &HashMap<String, String>) -> String {
    let mut result = text.to_string();
    for (key, value) in blocks {
        result = result.replace(key.as_str(), value);
    }
    result
}

// ---------------------------------------------------------------------------
// Logic density heuristic
// ---------------------------------------------------------------------------

static LOGIC_MARKERS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)\b(?:if\s+and\s+only\s+if|if\s+.+?\s+then\s+.+?\s+else|but\s+only|but\s+not|except\s+when|unless|whereas|provided\s+that|on\s+the\s+condition|iff|xor|mutually\s+exclusive|necessary\s+and\s+sufficient|contrapositive|thread.safe|race\s+condition|deadlock|atomic|mutex|semaphore)\b"
    ).unwrap()
});

static IF_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?i)\bif\b").unwrap());
static NEG_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\bnot\b|\bnever\b|\bno\b").unwrap());
static ORDER_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\bfirst\b|\bthen\b|\bbefore\b|\bafter\b|\bnext\b").unwrap());

/// Return 0.0–1.0 score of how logic-heavy a prompt is.
pub fn compute_logic_density(text: &str) -> f64 {
    let word_count = text.split_whitespace().count();
    if word_count == 0 {
        return 0.0;
    }

    let markers = LOGIC_MARKERS.find_iter(text).count();
    let conditionals = IF_RE.find_iter(text).count();
    let negations = NEG_RE.find_iter(text).count();
    let ordering = ORDER_RE.find_iter(text).count();

    let signal = markers * 3 + conditionals * 2 + negations * 2 + ordering;
    let density = signal as f64 / word_count as f64;
    density.min(1.0)
}

/// Compute compression intensity from logic density.
/// Returns 1.0 for normal prompts, down to 0.3 for ultra-logic.
pub fn intensity_from_density(density: f64) -> f64 {
    if density > 0.15 {
        (1.0 - density * 2.0).max(0.3)
    } else {
        1.0
    }
}

/// Check if a prompt is too short for processing (< 15 words).
pub fn is_short_prompt(text: &str) -> bool {
    text.split_whitespace().count() < 15
}

// ---------------------------------------------------------------------------
// Negation detection (shared by dialect/symbol stages)
// ---------------------------------------------------------------------------

/// Negation words that block replacement of negation-sensitive patterns.
pub const NEGATION_WORDS: &[&str] = &[
    "not", "no", "never", "don't", "doesn't", "didn't", "cannot",
    "can't", "won't", "shouldn't", "mustn't", "isn't", "aren't",
    "wasn't", "weren't", "wouldn't", "haven't", "hasn't", "hadn't",
    "nor", "neither",
];

/// Check if any negation word appears in the 5 words before `match_start`.
pub fn has_negation_before(text: &str, match_start: usize) -> bool {
    let preceding = &text[..match_start];
    preceding
        .split_whitespace()
        .rev()
        .take(5)
        .any(|w| {
            let clean = w.trim_end_matches(|c: char| matches!(c, '.' | ',' | ';' | ':' | '!' | '?'));
            NEGATION_WORDS
                .iter()
                .any(|neg| clean.eq_ignore_ascii_case(neg))
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_fenced_code() {
        let input = "Fix this:\n```python\ndef hello():\n    pass\n```\nDone";
        let (text, blocks) = extract_code_blocks(input);
        assert!(!text.contains("def hello"));
        assert_eq!(blocks.len(), 1);
        let restored = restore_blocks(&text, &blocks);
        assert_eq!(restored, input);
    }

    #[test]
    fn extract_inline_code() {
        let input = "The function `calculate_total()` is broken";
        let (text, blocks) = extract_code_blocks(input);
        assert!(!text.contains("calculate_total"));
        assert_eq!(blocks.len(), 1);
        let restored = restore_blocks(&text, &blocks);
        assert_eq!(restored, input);
    }

    #[test]
    fn no_code_blocks() {
        let input = "Just a normal sentence";
        let (text, blocks) = extract_code_blocks(input);
        assert_eq!(text, input);
        assert!(blocks.is_empty());
    }

    #[test]
    fn keep_blocks_extracted() {
        let input = "Remove filler but [keep: exactly this phrase] stays";
        let (text, blocks) = extract_keep_blocks(input);
        assert!(!text.contains("exactly this phrase"));
        assert_eq!(blocks.len(), 1);
        let restored = restore_blocks(&text, &blocks);
        assert!(restored.contains("exactly this phrase"));
    }

    #[test]
    fn low_logic_returns_low_density() {
        let d = compute_logic_density("Please summarize the article about machine learning");
        assert!(d < 0.15, "Expected low density, got {}", d);
    }

    #[test]
    fn high_logic_returns_high_density() {
        let d = compute_logic_density(
            "If x > 0 then return true, but not if the mutex is locked. Unless the semaphore is released and the thread is safe, do not proceed."
        );
        assert!(d > 0.15, "Expected high density, got {}", d);
    }

    #[test]
    fn empty_returns_zero() {
        assert_eq!(compute_logic_density(""), 0.0);
    }

    #[test]
    fn intensity_normal() {
        assert_eq!(intensity_from_density(0.05), 1.0);
    }

    #[test]
    fn intensity_reduced() {
        let i = intensity_from_density(0.3);
        assert!(i < 1.0 && i >= 0.3);
    }

    #[test]
    fn short_prompt_detection() {
        assert!(is_short_prompt("Hello world"));
        assert!(!is_short_prompt("This is a longer prompt that has many words and should not be considered short at all"));
    }

    #[test]
    fn negation_before_detected() {
        assert!(has_negation_before("do not act as a therapist", 7)); // before "act"
    }
}
