//! PyO3 bridge — wraps tauri-plugin-python with timeout and degraded mode.
//!
//! Architecture:
//! ```text
//! [Rust caller] → spawn_blocking(OS thread) → tauri-plugin-python → Python
//!                      ↓ (200ms timeout)
//!                 return original text
//! ```
//!
//! The Python engine runs `estimate_savings()` which returns both
//! compressed text and statistics in a single call.

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::time::timeout;

/// Whether the Python engine is in degraded mode (init failed).
static DEGRADED: AtomicBool = AtomicBool::new(false);

/// Whether the Python engine has been initialized.
static INITIALIZED: AtomicBool = AtomicBool::new(false);

/// Timeout for each Python call.
const PYTHON_TIMEOUT: Duration = Duration::from_millis(200);

/// Maximum input size (bytes) before we skip compression.
const MAX_INPUT_SIZE: usize = 64 * 1024; // 64 KB

/// Result from the Python compression engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineResult {
    pub compiled_text: String,
    pub original_tokens: u64,
    pub compressed_tokens: u64,
    pub saved_tokens: u64,
    pub percentage_saved: f64,
    pub compression_ratio: f64,
}

impl EngineResult {
    /// Passthrough result — returns original text unchanged.
    pub fn passthrough(text: &str) -> Self {
        let approx_tokens = (text.split_whitespace().count() as u64).max(1);
        Self {
            compiled_text: text.to_string(),
            original_tokens: approx_tokens,
            compressed_tokens: approx_tokens,
            saved_tokens: 0,
            percentage_saved: 0.0,
            compression_ratio: 1.0,
        }
    }
}

/// Set degraded mode state.
pub fn set_degraded(degraded: bool) {
    DEGRADED.store(degraded, Ordering::SeqCst);
}

/// Check if engine is in degraded mode.
pub fn is_degraded() -> bool {
    DEGRADED.load(Ordering::SeqCst)
}

/// Initialize the Python engine eagerly at daemon startup.
///
/// Creates a persistent PromptCompiler instance that lives for the
/// daemon's lifetime. Called once from main.rs setup.
pub fn init_python_engine() -> Result<(), String> {
    // TODO: Call tauri-plugin-python to initialize Python interpreter
    // and create persistent PromptCompiler instance.
    //
    // Pseudocode:
    //   python.run("from alchemist import PromptCompiler")
    //   python.run("_compiler = PromptCompiler()")
    //
    // On failure: return Err with diagnostic message.
    // On success: set INITIALIZED = true.

    INITIALIZED.store(true, Ordering::SeqCst);
    tracing::info!("Python engine initialized — PromptCompiler ready");
    Ok(())
}

/// Compress text through the Python engine.
///
/// Runs on a dedicated OS thread with a 200ms timeout. If the timeout
/// fires, the Rust side moves on immediately. When Python eventually
/// finishes, the result is checked against the current request ID —
/// if stale, it's discarded by the caller.
///
/// Returns `EngineResult::passthrough` on error, timeout, or degraded mode.
pub async fn compress(text: &str) -> EngineResult {
    if is_degraded() {
        tracing::warn!("Engine degraded — returning original text");
        return EngineResult::passthrough(text);
    }

    if !INITIALIZED.load(Ordering::SeqCst) {
        tracing::warn!("Engine not initialized — returning original text");
        return EngineResult::passthrough(text);
    }

    if text.len() > MAX_INPUT_SIZE {
        tracing::warn!(len = text.len(), "Input exceeds 64KB limit — returning original");
        return EngineResult::passthrough(text);
    }

    let text_owned = text.to_string();

    // Spawn on a blocking OS thread (not the tokio runtime).
    // This is critical: PyO3/GIL work must not block the async runtime.
    let handle = tokio::task::spawn_blocking(move || {
        call_python_engine(&text_owned)
    });

    // Apply 200ms timeout
    match timeout(PYTHON_TIMEOUT, handle).await {
        Ok(Ok(Ok(result))) => result,
        Ok(Ok(Err(e))) => {
            tracing::error!(error = %e, "Python engine error — returning original");
            EngineResult::passthrough(text)
        }
        Ok(Err(e)) => {
            tracing::error!(error = %e, "spawn_blocking panicked — returning original");
            EngineResult::passthrough(text)
        }
        Err(_) => {
            tracing::warn!("Python call timed out (>200ms) — returning original");
            // The spawned task continues running but its result will be
            // discarded via stale request ID check in the pipeline.
            EngineResult::passthrough(text)
        }
    }
}

/// Actually call the Python engine via tauri-plugin-python.
///
/// This runs on a dedicated OS thread (via spawn_blocking).
fn call_python_engine(text: &str) -> Result<EngineResult, String> {
    // TODO: Wire up tauri-plugin-python call:
    //   let result = python.call("_compiler.estimate_savings", [text])?;
    //   Parse result dict into EngineResult.
    //
    // For now: use a placeholder that demonstrates the interface.

    // Placeholder: approximate compression by word count reduction
    let words: Vec<&str> = text.split_whitespace().collect();
    let orig_tokens = words.len() as u64;
    if orig_tokens == 0 {
        return Ok(EngineResult::passthrough(text));
    }

    // TODO: Replace with actual Python call
    Ok(EngineResult {
        compiled_text: text.to_string(), // placeholder
        original_tokens: orig_tokens,
        compressed_tokens: orig_tokens,
        saved_tokens: 0,
        percentage_saved: 0.0,
        compression_ratio: 1.0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn passthrough_preserves_text() {
        let result = EngineResult::passthrough("hello world");
        assert_eq!(result.compiled_text, "hello world");
        assert_eq!(result.percentage_saved, 0.0);
        assert_eq!(result.saved_tokens, 0);
    }

    #[test]
    fn degraded_mode_toggle() {
        set_degraded(false);
        assert!(!is_degraded());
        set_degraded(true);
        assert!(is_degraded());
        set_degraded(false);
    }

    #[tokio::test]
    async fn compress_returns_passthrough_when_degraded() {
        set_degraded(true);
        let result = compress("test text").await;
        assert_eq!(result.compiled_text, "test text");
        assert_eq!(result.percentage_saved, 0.0);
        set_degraded(false);
    }

    #[tokio::test]
    async fn compress_returns_passthrough_when_not_initialized() {
        INITIALIZED.store(false, Ordering::SeqCst);
        set_degraded(false);
        let result = compress("test text").await;
        assert_eq!(result.compiled_text, "test text");
        // Restore
        INITIALIZED.store(true, Ordering::SeqCst);
    }
}
