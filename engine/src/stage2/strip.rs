//! Stage 2: Article/connector stripping — removes stop words for machine consumption.

use std::sync::LazyLock;

use regex::Regex;

/// Conservative stop-word set — excludes semantically meaningful words.
const STOP_WORDS: &[&str] = &[
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "which", "who", "whom", "these", "those", "am", "its",
    "of", "with", "at", "by", "into",
    "above", "below", "between",
    "off", "over", "under", "again", "further",
    "here", "there", "where",
    "each", "few", "most", "other", "some", "such",
    "same", "very", "just",
];

/// Words that LOOK like stop-words but carry semantic weight. Never strip.
const PROTECTED_WORDS: &[&str] = &[
    // Negation
    "not", "no", "never", "none", "neither", "nor", "nothing",
    "don't", "doesn't", "didn't", "cannot", "can't", "won't",
    "shouldn't", "mustn't", "isn't", "aren't", "wasn't", "weren't",
    "wouldn't", "haven't", "hasn't", "hadn't",
    // Temporal / ordering
    "before", "after", "then", "first", "last", "next", "until", "once",
    "during", "while", "when",
    // Logic / conditional
    "if", "else", "but", "and", "or", "only", "both", "either",
    "because", "so", "than", "though", "although", "unless", "whether",
    // Modality
    "should", "shall", "must", "will", "would", "may", "might",
    "can", "could",
    // Quantity / identity
    "all", "any", "every", "this", "that", "it",
    // Prepositions with meaning in instructions
    "to", "from", "in", "on", "for", "as", "out", "through",
    // Code keywords
    "return", "import", "class", "def", "true", "false", "null",
    "select", "where", "join", "group", "order", "limit", "insert",
    "update", "delete", "create", "drop", "alter", "index",
];

/// Compiled stop-word regex.
static STOP_RE: LazyLock<Regex> = LazyLock::new(|| {
    let safe_stops: Vec<&&str> = STOP_WORDS
        .iter()
        .filter(|w| !PROTECTED_WORDS.contains(w))
        .collect();
    let mut sorted: Vec<&str> = safe_stops.into_iter().copied().collect();
    sorted.sort_by(|a, b| b.len().cmp(&a.len()));
    let pattern = sorted
        .iter()
        .map(|w| regex::escape(w))
        .collect::<Vec<_>>()
        .join("|");
    Regex::new(&format!(r"(?i)\b(?:{})\b", pattern)).unwrap()
});

static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());
static SPACE_BEFORE_PUNCT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r" +([,.:;!?])").unwrap());

/// Strip stop words. Intensity < 0.1 skips entirely.
pub fn stage_strip(text: &str, intensity: f64) -> String {
    if intensity < 0.1 {
        return text.to_string();
    }

    let mut result = STOP_RE.replace_all(text, "").into_owned();
    result = MULTISPACE_RE.replace_all(&result, " ").into_owned();
    result = SPACE_BEFORE_PUNCT.replace_all(&result, "$1").into_owned();

    let lines: Vec<&str> = result.lines().map(|l| l.trim()).collect();
    result = lines.join("\n");
    result.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_stop_words() {
        let result = stage_strip("The analysis of the data was performed with the tools", 1.0);
        assert_eq!(result, "analysis data performed tools");
    }

    #[test]
    fn preserves_protected() {
        let result = stage_strip("If the value is not valid then return an error", 1.0);
        assert!(result.contains("If"));
        assert!(result.contains("not"));
        assert!(result.contains("then"));
        assert!(result.contains("return"));
    }

    #[test]
    fn zero_intensity_skips() {
        let result = stage_strip("The quick brown fox", 0.0);
        assert_eq!(result, "The quick brown fox");
    }
}
