//! Code block extraction — protects code from compression.

use std::collections::HashMap;
use std::sync::LazyLock;

use regex::Regex;

/// Sentinel format for extracted code blocks.
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

/// Restore code blocks from sentinels.
pub fn restore_blocks(text: &str, blocks: &HashMap<String, String>) -> String {
    let mut result = text.to_string();
    for (key, value) in blocks {
        result = result.replace(key.as_str(), value);
    }
    result
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
}
