//! Quality scorer — rates prompt quality on a 0–100 scale.
//!
//! Dimensions:
//! - Specificity: does it say exactly what it wants?
//! - Conciseness: is every word earning its place?
//! - Structure: is it well-organised?
//! - Completeness: does it include necessary constraints?

use std::sync::LazyLock;

use regex::Regex;

/// Quality score breakdown.
#[derive(Debug, Clone)]
pub struct QualityScore {
    /// Overall score 0–100.
    pub total: u32,
    /// Specificity sub-score 0–25.
    pub specificity: u32,
    /// Conciseness sub-score 0–25.
    pub conciseness: u32,
    /// Structure sub-score 0–25.
    pub structure: u32,
    /// Completeness sub-score 0–25.
    pub completeness: u32,
}

// Specificity indicators
static VAGUE_WORDS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:something|stuff|things|somehow|kind of|sort of|a lot|various|etc|basically)\b").unwrap()
});
static SPECIFIC_WORDS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:exactly|specifically|precisely|must|always|never|only|required)\b").unwrap()
});
static IMPERATIVE_VERBS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)^(?:write|create|build|implement|fix|add|remove|update|explain|list|compare|analyze|convert|generate|design|optimize)\b").unwrap()
});

// Conciseness indicators
static FILLER_WORDS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:just|really|basically|actually|simply|literally|quite|rather|pretty much|I was wondering|could you please|I want you to|I need you to|please make sure|thank you|thanks)\b").unwrap()
});

// Structure indicators
static HAS_NEWLINES: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\n").unwrap());
static HAS_LISTS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^[-*\d]+[.)]\s").unwrap());
static HAS_CONSTRAINTS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:must|should|only|not|never|always|do not|make sure|ensure|constraint|requirement|limit)\b").unwrap()
});

// Completeness indicators
static HAS_FORMAT_SPEC: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:format|json|csv|table|markdown|code|list|array|object|html|xml|yaml)\b").unwrap()
});
static HAS_CONTEXT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:context|background|given|assuming|scenario|use case|example)\b").unwrap()
});

/// Score a prompt's quality on 0–100 scale.
pub fn score(text: &str) -> QualityScore {
    let words: Vec<&str> = text.split_whitespace().collect();
    let word_count = words.len();

    if word_count == 0 {
        return QualityScore { total: 0, specificity: 0, conciseness: 0, structure: 0, completeness: 0 };
    }

    // --- Specificity (0–25) ---
    let vague_count = VAGUE_WORDS.find_iter(text).count();
    let specific_count = SPECIFIC_WORDS.find_iter(text).count();
    let starts_imperative = IMPERATIVE_VERBS.is_match(text.trim());

    let mut specificity: f64 = 12.0; // baseline
    specificity -= vague_count as f64 * 3.0;
    specificity += specific_count as f64 * 2.0;
    if starts_imperative { specificity += 5.0; }
    if word_count > 5 { specificity += 3.0; }
    let specificity = specificity.clamp(0.0, 25.0) as u32;

    // --- Conciseness (0–25) ---
    let filler_count = FILLER_WORDS.find_iter(text).count();
    let filler_ratio = filler_count as f64 / word_count as f64;

    let mut conciseness: f64 = 20.0; // start high, penalize filler
    conciseness -= filler_ratio * 60.0;
    // Penalize very long prompts with high filler
    if word_count > 50 && filler_ratio > 0.1 { conciseness -= 5.0; }
    // Reward concise prompts
    if word_count < 30 && filler_count == 0 { conciseness += 5.0; }
    let conciseness = conciseness.clamp(0.0, 25.0) as u32;

    // --- Structure (0–25) ---
    let has_structure = HAS_NEWLINES.is_match(text);
    let has_lists = HAS_LISTS.is_match(text);
    let has_constraints = HAS_CONSTRAINTS.is_match(text);

    let mut structure: f64 = 10.0;
    if has_structure { structure += 5.0; }
    if has_lists { structure += 5.0; }
    if has_constraints { structure += 5.0; }
    // Short prompts don't need structure
    if word_count < 20 { structure += 5.0; }
    let structure = structure.clamp(0.0, 25.0) as u32;

    // --- Completeness (0–25) ---
    let has_format = HAS_FORMAT_SPEC.is_match(text);
    let has_context = HAS_CONTEXT.is_match(text);

    let mut completeness: f64 = 10.0;
    if has_format { completeness += 7.0; }
    if has_context { completeness += 5.0; }
    if has_constraints { completeness += 3.0; }
    if word_count > 10 { completeness += 2.0; }
    let completeness = completeness.clamp(0.0, 25.0) as u32;

    let total = specificity + conciseness + structure + completeness;

    QualityScore { total, specificity, conciseness, structure, completeness }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_scores_zero() {
        let s = score("");
        assert_eq!(s.total, 0);
    }

    #[test]
    fn good_prompt_scores_high() {
        let s = score("Write a Python function that takes a list of integers and returns only the even numbers. Return the result as a JSON array.");
        assert!(s.total > 60, "Good prompt should score >60, got {}", s.total);
    }

    #[test]
    fn vague_prompt_scores_low() {
        let s = score("Hey, I was wondering if you could basically just do something with the stuff and things I need. Could you please help me out? Thanks!");
        assert!(s.total < 50, "Vague prompt should score <50, got {}", s.total);
    }

    #[test]
    fn sharpened_scores_higher_than_original() {
        let original = score("Hey, I was wondering if you could help me out with something. I need you to take this list and turn it into a JSON object. Please make sure the JSON is valid. Thank you so much!");
        let sharpened = score("Convert this list into a JSON object with valid, properly indented JSON.");
        assert!(
            sharpened.total > original.total,
            "Sharpened ({}) should score higher than original ({})",
            sharpened.total, original.total
        );
    }

    #[test]
    fn score_components_sum_to_total() {
        let s = score("Write a function to sort a list");
        assert_eq!(s.total, s.specificity + s.conciseness + s.structure + s.completeness);
    }
}
