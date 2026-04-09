//! Stage 1: Verbose→concise pattern rewriting.
//!
//! Replaces wordy constructions with shorter, clearer equivalents.
//! Output remains human-readable — this is the visible improvement.

use std::sync::LazyLock;

use regex::Regex;

/// A rewrite rule: pattern → replacement (both human-readable).
struct RewriteRule {
    pattern: Regex,
    replacement: &'static str,
}

/// Verbose→concise rewrite rules.
static REWRITE_RULES: LazyLock<Vec<RewriteRule>> = LazyLock::new(|| {
    let rules = [
        // Verbose constructions → concise equivalents
        (r"(?i)\bin order to\b", "to"),
        (r"(?i)\bdue to the fact that\b", "because"),
        (r"(?i)\bfor the purpose of\b", "to"),
        (r"(?i)\bwith regard to\b", "about"),
        (r"(?i)\bwith respect to\b", "about"),
        (r"(?i)\bin the event that\b", "if"),
        (r"(?i)\bat this point in time\b", "now"),
        (r"(?i)\bat the present time\b", "now"),
        (r"(?i)\bat the end of the day\b", "ultimately"),
        (r"(?i)\bon a daily basis\b", "daily"),
        (r"(?i)\bon a regular basis\b", "regularly"),
        (r"(?i)\ba large number of\b", "many"),
        (r"(?i)\ba significant number of\b", "many"),
        (r"(?i)\ba majority of\b", "most"),
        (r"(?i)\bin close proximity to\b", "near"),
        (r"(?i)\bhas the ability to\b", "can"),
        (r"(?i)\bis able to\b", "can"),
        (r"(?i)\bis capable of\b", "can"),
        (r"(?i)\bin spite of the fact that\b", "although"),
        (r"(?i)\bregardless of the fact that\b", "although"),
        (r"(?i)\bfor the reason that\b", "because"),
        (r"(?i)\bby means of\b", "with"),
        (r"(?i)\bin the process of\b", "while"),
        (r"(?i)\bin the near future\b", "soon"),
        (r"(?i)\bprior to\b", "before"),
        (r"(?i)\bsubsequent to\b", "after"),
        (r"(?i)\bin addition to\b", "besides"),
        (r"(?i)\bas a consequence of\b", "because of"),
        (r"(?i)\btake into consideration\b", "consider"),
        (r"(?i)\btake into account\b", "consider"),
        (r"(?i)\bmake a decision\b", "decide"),
        (r"(?i)\bgive an explanation\b", "explain"),
        (r"(?i)\bprovide an explanation\b", "explain"),
        (r"(?i)\bconduct an analysis\b", "analyze"),
        (r"(?i)\bperform an analysis\b", "analyze"),
        (r"(?i)\bmake an attempt\b", "try"),
        (r"(?i)\bmake modifications to\b", "modify"),
        (r"(?i)\bmake changes to\b", "change"),
        (r"(?i)\bmake improvements to\b", "improve"),
        (r"(?i)\bcome to the conclusion\b", "conclude"),
        (r"(?i)\beach and every\b", "every"),
        (r"(?i)\bfirst and foremost\b", "first"),
        (r"(?i)\bone and only\b", "only"),
        (r"(?i)\bbasically,?\s*", ""),
        (r"(?i)\bessentially,?\s*", ""),
        (r"(?i)\bactually,?\s*", ""),
        (r"(?i)\bliterally\b", ""),
        // Vague hedges in prompts
        (r"(?i)\bwrite some\b", "write"),
        (r"(?i)\bmaybe you could\b", ""),
        (r"(?i)\bperhaps you could\b", ""),
        (r"(?i)\bI think you should\b", ""),
        (r"(?i)\bI believe you should\b", ""),
    ];
    rules
        .iter()
        .map(|(pattern, replacement)| RewriteRule {
            pattern: Regex::new(pattern).unwrap(),
            replacement,
        })
        .collect()
});

static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());

/// Rewrite verbose constructions into concise equivalents.
///
/// Output is human-readable — the user sees and approves this.
pub fn rewrite(text: &str) -> String {
    let mut result = text.to_string();

    for rule in REWRITE_RULES.iter() {
        result = rule.pattern.replace_all(&result, rule.replacement).into_owned();
    }

    // Clean up whitespace artifacts
    result = MULTISPACE_RE.replace_all(&result, " ").into_owned();
    result.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn in_order_to_becomes_to() {
        let result = rewrite("In order to fix this bug, you need to change the code");
        assert!(result.contains("to fix"), "got: {}", result);
        assert!(!result.contains("In order to"));
    }

    #[test]
    fn due_to_the_fact_becomes_because() {
        let result = rewrite("The test fails due to the fact that the mock is wrong");
        assert!(result.contains("because"));
        assert!(!result.contains("due to the fact that"));
    }

    #[test]
    fn multiple_rewrites() {
        let result = rewrite("In order to make a decision, take into consideration the data");
        assert!(result.contains("to decide") || result.contains("To decide"), "got: {}", result);
        assert!(result.contains("consider"));
    }

    #[test]
    fn preserves_meaningful_text() {
        let input = "Implement binary search with O(log n) complexity";
        assert_eq!(rewrite(input), input);
    }

    #[test]
    fn removes_filler_words() {
        let result = rewrite("Basically, the function is able to sort the list");
        assert!(!result.contains("Basically"));
        assert!(result.contains("can sort"));
    }
}
