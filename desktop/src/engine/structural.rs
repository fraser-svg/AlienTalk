//! Stage 3: Structural Minification — JSON minification and list collapsing.

use std::sync::LazyLock;

use regex::Regex;

static MULTILINE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\n{3,}").unwrap());
static MULTISPACE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[ \t]{2,}").unwrap());
static NUMBERED_LIST_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^(\d+)\.\s+").unwrap());
static BULLET_LIST_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[-*]\s+").unwrap());

/// Minify JSON objects/arrays found in text.
fn minify_json_blocks(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    let mut chars = text.char_indices().peekable();

    while let Some(&(i, ch)) = chars.peek() {
        if ch == '{' || ch == '[' {
            let open = ch;
            let close = if ch == '{' { '}' } else { ']' };
            let mut depth = 1i32;
            let mut j = i + ch.len_utf8();
            // Scan forward to find matching close bracket
            let mut scan = text[j..].char_indices();
            while let Some((offset, c)) = scan.next() {
                if c == open {
                    depth += 1;
                } else if c == close {
                    depth -= 1;
                }
                if depth == 0 {
                    j += offset + c.len_utf8();
                    break;
                }
            }
            if depth == 0 {
                let candidate = &text[i..j];
                // Try parsing as JSON and re-serializing compact
                if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(candidate) {
                    if let Ok(minified) = serde_json::to_string(&parsed) {
                        result.push_str(&minified);
                        // Advance the main iterator past the JSON block
                        while let Some(&(idx, _)) = chars.peek() {
                            if idx >= j {
                                break;
                            }
                            chars.next();
                        }
                        continue;
                    }
                }
            }
        }
        result.push(ch);
        chars.next();
    }
    result
}

/// Collapse verbose numbered/bulleted lists into compact form.
fn collapse_lists(text: &str) -> String {
    let result = NUMBERED_LIST_RE.replace_all(text, "${1})").to_string();
    BULLET_LIST_RE.replace_all(&result, "•").to_string()
}

/// Apply structural minification. Intensity < 0.1 skips.
pub fn stage_structural(text: &str, intensity: f64) -> String {
    if intensity < 0.1 {
        return text.to_string();
    }
    let mut result = minify_json_blocks(text);
    result = collapse_lists(&result);
    result = MULTILINE_RE.replace_all(&result, "\n\n").into_owned();
    result = MULTISPACE_RE.replace_all(&result, " ").into_owned();
    result.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minify_json() {
        let input = r#"{"name": "John", "age": 30, "city": "New York"}"#;
        let result = stage_structural(input, 1.0);
        assert_eq!(result, r#"{"age":30,"city":"New York","name":"John"}"#);
    }

    #[test]
    fn collapse_numbered_list() {
        let input = "1. First item\n2. Second item\n3. Third item";
        let result = stage_structural(input, 1.0);
        assert!(result.contains("1)First"));
        assert!(result.contains("2)Second"));
    }

    #[test]
    fn collapse_bullet_list() {
        let input = "- Alpha\n- Beta\n- Gamma";
        let result = stage_structural(input, 1.0);
        assert!(result.contains("•Alpha"));
    }

    #[test]
    fn zero_intensity_skips() {
        let input = r#"{"a": 1}"#;
        let result = stage_structural(input, 0.0);
        assert_eq!(result, input);
    }

    #[test]
    fn nested_json() {
        let input = r#"{"outer": {"inner": 1}, "arr": [1, 2]}"#;
        let result = stage_structural(input, 1.0);
        assert!(result.contains("\"inner\":1"));
        assert!(result.contains("\"arr\":[1,2]"));
    }

    #[test]
    fn json_array() {
        let input = r#"[1, 2, "three", true]"#;
        let result = stage_structural(input, 1.0);
        assert_eq!(result, r#"[1,2,"three",true]"#);
    }

    #[test]
    fn json_in_prose() {
        let input = r#"The schema is {"name": "Alice"} and done"#;
        let result = stage_structural(input, 1.0);
        assert!(result.contains(r#"{"name":"Alice"}"#));
        assert!(result.starts_with("The schema is"));
    }
}
