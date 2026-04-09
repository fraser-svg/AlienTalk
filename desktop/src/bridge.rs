//! Compression bridge — wraps the Rust engine with timeout and degraded mode.
//!
//! Architecture (v0.3):
//! ```text
//! [Rust caller] → spawn_blocking(OS thread) → engine::compile() → result
//!                      ↓ (200ms timeout)
//!                 return original text
//! ```
//!
//! The Python/PyO3 bridge has been replaced with a pure Rust engine.

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::time::timeout;

use crate::engine;

/// Whether the engine is in degraded mode.
static DEGRADED: AtomicBool = AtomicBool::new(false);

/// Whether the engine has been initialized.
static INITIALIZED: AtomicBool = AtomicBool::new(false);

/// Timeout for each compression call.
const ENGINE_TIMEOUT: Duration = Duration::from_millis(200);

/// Maximum input size (bytes) before we skip compression.
const MAX_INPUT_SIZE: usize = 64 * 1024; // 64 KB

/// Result from the compression engine (serializable for Tauri IPC).
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

/// Initialize the Rust compression engine.
///
/// Warms up lazy statics (regex compilation) so first request is fast.
pub fn init_engine() -> Result<(), String> {
    // Force lazy static initialization by running a trivial compilation
    let _ = engine::compile("warmup");
    INITIALIZED.store(true, Ordering::SeqCst);
    tracing::info!("Rust compression engine initialized");
    Ok(())
}

/// Compress text through the Rust engine.
///
/// Runs on a dedicated OS thread with a 200ms timeout to avoid
/// blocking the async runtime on large inputs.
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

    // Spawn on a blocking OS thread (regex work can be CPU-heavy on large inputs).
    let handle = tokio::task::spawn_blocking(move || {
        let result = engine::estimate_savings(&text_owned);
        EngineResult {
            compiled_text: result.compiled_text,
            original_tokens: result.original_tokens,
            compressed_tokens: result.compressed_tokens,
            saved_tokens: result.saved_tokens,
            percentage_saved: result.percentage_saved,
            compression_ratio: result.compression_ratio,
        }
    });

    match timeout(ENGINE_TIMEOUT, handle).await {
        Ok(Ok(result)) => result,
        Ok(Err(e)) => {
            tracing::error!(error = %e, "spawn_blocking panicked — returning original");
            EngineResult::passthrough(text)
        }
        Err(_) => {
            tracing::warn!("Engine call timed out (>200ms) — returning original");
            EngineResult::passthrough(text)
        }
    }
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

    #[test]
    fn init_engine_succeeds() {
        assert!(init_engine().is_ok());
        assert!(INITIALIZED.load(Ordering::SeqCst));
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

    #[tokio::test]
    async fn compress_actually_compresses() {
        let _ = init_engine();
        set_degraded(false);
        let result = compress("I want you to explain how databases work").await;
        // Filler "I want you to" should be removed
        assert!(!result.compiled_text.contains("I want you to"));
        assert!(result.compiled_text.contains("explain"));
    }
}
