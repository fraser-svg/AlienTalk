//! Stage 2: Symbol compression — pattern→symbol replacement.
//!
//! Replaces common instruction patterns with short tokens that LLMs understand.
//! This is machine-facing and invisible to the user.

use std::sync::LazyLock;

use regex::Regex;

use crate::safety;

/// A single symbol entry: compiled regex, replacement string, negation-sensitive flag.
pub struct SymbolEntry {
    pub pattern: Regex,
    pub replacement: &'static str,
    pub neg_sensitive: bool,
}

/// Symbols used in compression that could appear in user text.
pub const COMPRESSION_SYMBOLS: &[&str] = &["Σ", "⇒", "∴", "⟺", "Δ", "↗", "↻", "⊂", "ƒ", "→"];

/// Escape sentinel for literal symbols in user text.
pub const ESCAPE_PREFIX: &str = "\x00ESC:";
pub const ESCAPE_SUFFIX: &str = "\x00";

/// Raw symbol map entries: (pattern_text, replacement, negation_sensitive).
/// Sorted longest-first to prevent partial matches.
const SYMBOL_MAP_RAW: &[(&str, &str, bool)] = &[
    // Filler removal (longest first)
    ("take this text and turn it into a json object with keys for", "Σ TEXT⇒{}", false),
    ("provide a detailed explanation", "Σ++", false),
    ("it should be noted that", "", false),
    ("i would like you to", "", false),
    ("strict adherence to constraints", "!strict", false),
    ("explain step by step", "CoT→", false),
    ("generate a list of", "⇒[]", false),
    ("classify the following", "⊂classify", false),
    ("extract the following", "⊂extract", false),
    ("rewrite the following", "↻", false),
    ("output in json format", "⇒{}", false),
    ("let's think about this", "CoT", false),
    ("as a numbered list", "⇒[#]", false),
    ("from the perspective of", "@pov:", false),
    ("under no circumstances", "!never", false),
    ("return only the code", "⇒code!", false),
    ("analyze and provide", "Δ→", false),
    ("compare and contrast", "⟺", false),
    ("evaluate whether", "⊂eval", false),
    ("could you please", "", false),
    ("please note that", "", false),
    ("i want you to", "", false),
    ("i need you to", "", false),
    ("can you please", "", false),
    ("i'd like you to", "", false),
    ("please ensure that", "!ensure", false),
    ("as a json object", "⇒{}", false),
    ("strict adherence", "!strict", false),
    ("format as markdown", "⇒md", false),
    ("do not deviate", "!strict", false),
    ("respond in json", "⇒{}", false),
    ("format as a table", "⇒table", false),
    ("format as a list", "⇒[]", false),
    ("as a bullet list", "⇒[]", false),
    ("do not include", "!omit", false),
    ("do not mention", "!omit", false),
    ("do not explain", "!omit explain", false),
    ("you must always", "!always", false),
    ("without exception", "!noexcept", false),
    ("convert to json", "⇒{}", false),
    ("convert to yaml", "⇒yaml", false),
    ("convert to csv", "⇒csv", false),
    ("output as code", "⇒code", false),
    ("chain of thought", "CoT", false),
    ("step by step", "CoT", false),
    ("make sure to", "!ensure", false),
    ("it is important that", "!ensure", false),
    ("keep it concise", "!brief", false),
    ("write a function", "ƒ", false),
    ("create a function", "ƒ", false),
    ("refactor the", "↻", false),
    ("translate to", "↗lang:", false),
    ("implement a", "impl:", true),
    ("be concise", "!brief", false),
    ("be specific", "!specific", false),
    ("in conclusion", "∴", false),
    ("for example", "e.g.", false),
    ("in other words", "i.e.", false),
    ("as a result", "∴", false),
    ("in summary", "Σ", false),
    ("summarize", "Σ", false),
    ("think step by step", "CoT", false),
    // Role/persona (negation-sensitive)
    ("you are an expert", "@expert", true),
    ("as an expert in", "@expert:", true),
    ("act as a", "@role:", true),
    ("pretend you are", "@role:", true),
    ("you are a", "@role:", true),
];

/// Compiled symbol entries, sorted longest-first.
pub static SYMBOL_ENTRIES: LazyLock<Vec<SymbolEntry>> = LazyLock::new(|| {
    let mut entries: Vec<(&str, &str, bool)> = SYMBOL_MAP_RAW.to_vec();
    entries.sort_by(|a, b| b.0.len().cmp(&a.0.len()));
    entries
        .iter()
        .map(|(key, replacement, neg_sensitive)| {
            let escaped = regex::escape(key);
            let pattern = Regex::new(&format!(r"(?i)\b{}\b", escaped))
                .unwrap_or_else(|_| Regex::new(&format!(r"(?i){}", escaped)).unwrap());
            SymbolEntry {
                pattern,
                replacement,
                neg_sensitive: *neg_sensitive,
            }
        })
        .collect()
});

/// Inverse map for decompilation (skip empty-string mappings).
pub static DECOMPILE_ENTRIES: LazyLock<Vec<(Regex, &'static str)>> = LazyLock::new(|| {
    let mut entries: Vec<(&str, &str)> = SYMBOL_MAP_RAW
        .iter()
        .filter(|(_, repl, _)| !repl.is_empty())
        .map(|(key, repl, _)| (*repl, *key))
        .collect();
    entries.sort_by(|a, b| b.0.len().cmp(&a.0.len()));
    entries
        .into_iter()
        .map(|(sym, expansion)| {
            let pattern = Regex::new(&regex::escape(sym)).unwrap();
            (pattern, expansion)
        })
        .collect()
});

/// Apply symbol compression. `intensity` 0.0=skip, 1.0=full.
pub fn stage_symbols(text: &str, intensity: f64) -> String {
    if intensity < 0.1 {
        return text.to_string();
    }

    let mut result = text.to_string();
    for entry in SYMBOL_ENTRIES.iter() {
        if entry.neg_sensitive {
            if entry.pattern.find(&result).is_none() {
                continue;
            }
            let src = result.clone();
            let mut new_result = String::new();
            let mut last_end = 0;
            for m in entry.pattern.find_iter(&src) {
                new_result.push_str(&src[last_end..m.start()]);
                if safety::has_negation_before(&src, m.start()) {
                    new_result.push_str(m.as_str());
                } else {
                    new_result.push_str(entry.replacement);
                }
                last_end = m.end();
            }
            new_result.push_str(&src[last_end..]);
            result = new_result;
        } else {
            let replaced = entry.pattern.replace_all(&result, entry.replacement);
            if let std::borrow::Cow::Owned(s) = replaced {
                result = s;
            }
        }
    }
    result
}

/// Escape literal compression symbols in user text.
pub fn escape_literal_symbols(text: &str) -> String {
    let mut result = text.to_string();
    for sym in COMPRESSION_SYMBOLS {
        if result.contains(sym) {
            result = result.replace(sym, &format!("{}{}{}", ESCAPE_PREFIX, sym, ESCAPE_SUFFIX));
        }
    }
    result
}

/// Restore escaped literal symbols.
pub fn unescape_literal_symbols(text: &str) -> String {
    let mut result = text.to_string();
    for sym in COMPRESSION_SYMBOLS {
        result = result.replace(
            &format!("{}{}{}", ESCAPE_PREFIX, sym, ESCAPE_SUFFIX),
            sym,
        );
    }
    result
}

/// Decompile: reverse symbolic mapping for human readability.
pub fn decompile(compressed: &str) -> String {
    let mut text = compressed.to_string();
    for (pattern, expansion) in DECOMPILE_ENTRIES.iter() {
        text = pattern.replace_all(&text, *expansion).into_owned();
    }
    text
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filler_removal() {
        let result = stage_symbols("I want you to explain how databases work", 1.0);
        assert_eq!(result.trim(), "explain how databases work");
    }

    #[test]
    fn symbolic_mapping() {
        let result = stage_symbols("Think step by step about this", 1.0);
        assert!(result.contains("CoT"));
    }

    #[test]
    fn negation_blocks_mapping() {
        let result = stage_symbols("Do not act as a therapist", 1.0);
        assert!(result.contains("act as"), "negation should block @role: mapping");
    }

    #[test]
    fn escape_roundtrip() {
        let text = "The equation uses Σ notation";
        let escaped = escape_literal_symbols(text);
        assert!(escaped.contains(ESCAPE_PREFIX));
        let restored = unescape_literal_symbols(&escaped);
        assert_eq!(restored, text);
    }

    #[test]
    fn zero_intensity_skips() {
        let result = stage_symbols("I want you to explain", 0.0);
        assert_eq!(result, "I want you to explain");
    }
}
