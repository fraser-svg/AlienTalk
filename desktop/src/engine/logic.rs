//! Logic density heuristic — detects high-logic prompts and adjusts compression intensity.

use std::sync::LazyLock;

use regex::Regex;

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
    let words: Vec<&str> = text.split_whitespace().collect();
    if words.is_empty() {
        return 0.0;
    }

    let markers = LOGIC_MARKERS.find_iter(text).count();
    let conditionals = IF_RE.find_iter(text).count();
    let negations = NEG_RE.find_iter(text).count();
    let ordering = ORDER_RE.find_iter(text).count();

    let signal = markers * 3 + conditionals * 2 + negations * 2 + ordering;
    let density = signal as f64 / words.len() as f64;
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

#[cfg(test)]
mod tests {
    use super::*;

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
}
