//! Stage 1: Filler removal — strips hedge phrases and politeness filler.
//!
//! Human-readable output: removes unnecessary words while keeping the prompt
//! readable and clear. This is the "Grammarly moment" — user sees the improvement.

use std::sync::LazyLock;

use regex::Regex;

/// Hedge phrases to remove entirely.
static HEDGE_PHRASES: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    let patterns = [
        // Long hedges (match longest first)
        r"(?i)\bI was wondering if you could\b",
        r"(?i)\bI was wondering if\b",
        r"(?i)\bI would really appreciate it if you could\b",
        r"(?i)\bI would appreciate it if you could\b",
        r"(?i)\bI would really like you to\b",
        r"(?i)\bI would like you to\b",
        r"(?i)\bwould it be possible for you to\b",
        r"(?i)\bwould it be possible to\b",
        r"(?i)\bdo you think you could\b",
        r"(?i)\bcould you possibly\b",
        r"(?i)\bcould you help me with\b",
        r"(?i)\bcould you help me\b",
        r"(?i)\bif you don't mind,?\s*\b",
        r"(?i)\bif it's not too much trouble,?\s*\b",
        r"(?i)\bI'd really appreciate if\b",
        r"(?i)\bplease make sure to\b",
        r"(?i)\bplease make sure\b",
        r"(?i)\bit is important that\b",
        // Medium hedges
        r"(?i)\bI'd like you to\b",
        r"(?i)\bI would like to\b",
        r"(?i)\bI want you to\b",
        r"(?i)\bI need you to\b",
        r"(?i)\bcould you please\b",
        r"(?i)\bcan you please\b",
        r"(?i)\bplease note that\b",
        r"(?i)\bit should be noted that\b",
        r"(?i)\bI was hoping you could\b",
        r"(?i)\bI'm hoping you can\b",
    ];
    patterns
        .iter()
        .map(|p| Regex::new(p).unwrap())
        .collect()
});

/// Politeness filler to remove.
static POLITENESS_FILLER: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    let patterns = [
        r"(?i)\bthank you so much[!.]?\s*",
        r"(?i)\bthanks in advance[!.]?\s*",
        r"(?i)\bthank you for your help[!.]?\s*",
        r"(?i)\bthanks for your help[!.]?\s*",
        r"(?i)\bI appreciate your help[!.]?\s*",
        r"(?i)\bI really appreciate it[!.]?\s*",
        r"(?i)\bthanks[!.]?\s*$",
        r"(?i)\bthank you[!.]?\s*$",
        r"(?i)^hey,?\s*",
        r"(?i)^hi,?\s*",
        r"(?i)^hello,?\s*",
    ];
    patterns
        .iter()
        .map(|p| Regex::new(p).unwrap())
        .collect()
});

static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());

/// Remove hedge phrases and politeness filler from text.
///
/// Produces human-readable output — the user sees and approves this.
pub fn remove_filler(text: &str) -> String {
    let mut result = text.to_string();

    // Remove hedge phrases
    for re in HEDGE_PHRASES.iter() {
        result = re.replace_all(&result, "").into_owned();
    }

    // Remove politeness filler
    for re in POLITENESS_FILLER.iter() {
        result = re.replace_all(&result, "").into_owned();
    }

    // Clean up whitespace artifacts
    result = MULTISPACE_RE.replace_all(&result, " ").into_owned();
    result.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn removes_hedge_phrases() {
        let result = remove_filler("I was wondering if you could help me write a function");
        assert_eq!(result, "help me write a function");
    }

    #[test]
    fn removes_politeness() {
        let result = remove_filler("Write a function to sort a list. Thank you so much!");
        assert_eq!(result, "Write a function to sort a list.");
    }

    #[test]
    fn removes_greetings() {
        let result = remove_filler("Hey, can you please write a function");
        assert_eq!(result, "write a function");
    }

    #[test]
    fn preserves_meaningful_content() {
        let result = remove_filler("Explain how binary search works");
        assert_eq!(result, "Explain how binary search works");
    }

    #[test]
    fn removes_multiple_fillers() {
        let result = remove_filler(
            "Hi, I was wondering if you could please make sure to write a good function. Thanks in advance!"
        );
        assert!(result.contains("write a good function"));
        assert!(!result.contains("wondering"));
        assert!(!result.contains("Thanks"));
    }

    #[test]
    fn empty_input() {
        assert_eq!(remove_filler(""), "");
    }
}
