//! Stage 1: Text cleanup — normalization and structure tidying.
//!
//! Runs as part of Stage 1 (sharpen). Produces clean, human-readable text.

use std::sync::LazyLock;

use regex::Regex;

static ELLIPSIS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\.{4,}").unwrap());
static REPEATED_BANG_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"!{2,}").unwrap());
static REPEATED_QUESTION_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\?{2,}").unwrap());
static SPACE_BEFORE_PUNCT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s+([,.:;!?])").unwrap());
static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());
static MULTILINE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\n{3,}").unwrap());
static SENTENCE_CAP_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"([.!?])\s+([a-z])").unwrap());

/// Normalize repeated punctuation only (safe for code blocks).
///
/// Collapses `!!!!` → `!`, `????` → `?`, `....` → `...`
pub fn normalize_punctuation(text: &str) -> String {
    let mut result = text.to_string();
    result = ELLIPSIS_RE.replace_all(&result, "...").into_owned();
    result = REPEATED_BANG_RE.replace_all(&result, "!").into_owned();
    result = REPEATED_QUESTION_RE.replace_all(&result, "?").into_owned();
    result
}

/// Normalize and clean up text for human readability.
///
/// - Trim whitespace per line
/// - Fix sentence-initial capitalization
/// - Normalize repeated punctuation
/// - Collapse multiple spaces and blank lines
pub fn cleanup(text: &str) -> String {
    // Trim whitespace per line
    let lines: Vec<String> = text
        .lines()
        .map(|line| {
            let trimmed = line.trim().to_string();
            if trimmed.is_empty() {
                return trimmed;
            }
            // Capitalize first character if lowercase
            let mut chars = trimmed.chars();
            match chars.next() {
                Some(c) if c.is_ascii_lowercase() => {
                    let mut s = c.to_uppercase().to_string();
                    s.extend(chars);
                    s
                }
                _ => trimmed,
            }
        })
        .collect();

    let mut text = lines.join("\n");

    // Capitalize after sentence-ending punctuation within lines
    text = SENTENCE_CAP_RE
        .replace_all(&text, |caps: &regex::Captures| {
            let punct = &caps[1];
            let letter = caps[2].to_uppercase();
            format!("{} {}", punct, letter)
        })
        .into_owned();

    // Normalize repeated punctuation
    text = ELLIPSIS_RE.replace_all(&text, "...").into_owned();
    text = REPEATED_BANG_RE.replace_all(&text, "!").into_owned();
    text = REPEATED_QUESTION_RE.replace_all(&text, "?").into_owned();

    // Remove space before punctuation
    text = SPACE_BEFORE_PUNCT_RE.replace_all(&text, "$1").into_owned();

    // Collapse multiple spaces and blank lines
    text = MULTISPACE_RE.replace_all(&text, " ").into_owned();
    text = MULTILINE_RE.replace_all(&text, "\n\n").into_owned();

    text.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn collapses_punctuation() {
        assert_eq!(cleanup("Wait!!!! What???  Really....."), "Wait! What? Really...");
    }

    #[test]
    fn capitalizes_first_char() {
        assert_eq!(cleanup("hello world"), "Hello world");
    }

    #[test]
    fn trims_lines() {
        assert_eq!(cleanup("  hello  \n  world  "), "Hello\nWorld");
    }

    #[test]
    fn empty_input() {
        assert_eq!(cleanup(""), "");
    }

    #[test]
    fn multi_sentence_capitalization() {
        assert_eq!(cleanup("hello world. fix this."), "Hello world. Fix this.");
    }

    #[test]
    fn three_dot_ellipsis_preserved() {
        assert_eq!(cleanup("wait..."), "Wait...");
    }

    #[test]
    fn collapses_excessive_blank_lines() {
        assert_eq!(cleanup("Hello\n\n\n\nWorld"), "Hello\n\nWorld");
    }
}
