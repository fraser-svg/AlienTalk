//! Pre-compression text normalization.
//!
//! Runs after spell correction, before symbolic mapping.

use std::sync::LazyLock;

use regex::Regex;

static ELLIPSIS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\.{4,}").unwrap());
// regex crate doesn't support backreferences, so we match runs of each punct char directly
static REPEATED_BANG_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"!{2,}").unwrap());
static REPEATED_QUESTION_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\?{2,}").unwrap());
static SPACE_BEFORE_PUNCT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s+([,.:;!?])").unwrap());
static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());
static MULTILINE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\n{3,}").unwrap());
static SENTENCE_CAP_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"([.!?])\s+([a-z])").unwrap());

/// Normalize text before compression.
///
/// - Trim whitespace per line
/// - Fix sentence-initial capitalization
/// - Normalize repeated punctuation
/// - Collapse multiple spaces and blank lines
pub fn normalize(text: &str) -> String {
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
        assert_eq!(normalize("Wait!!!! What???  Really....."), "Wait! What? Really...");
    }

    #[test]
    fn capitalizes_first_char() {
        assert_eq!(normalize("hello world"), "Hello world");
    }

    #[test]
    fn trims_lines() {
        assert_eq!(normalize("  hello  \n  world  "), "Hello\nWorld");
    }

    #[test]
    fn empty_input() {
        assert_eq!(normalize(""), "");
    }

    #[test]
    fn multi_sentence_capitalization() {
        assert_eq!(normalize("hello world. fix this."), "Hello world. Fix this.");
    }

    #[test]
    fn three_dot_ellipsis_preserved() {
        assert_eq!(normalize("wait..."), "Wait...");
    }

    #[test]
    fn collapses_excessive_blank_lines() {
        assert_eq!(normalize("Hello\n\n\n\nWorld"), "Hello\n\nWorld");
    }
}
