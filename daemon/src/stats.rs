//! Stats tracker — persists cumulative compression statistics.
//!
//! Stored at ~/.alientalk/stats.json. Updated after every successful
//! compression. Exposed via Tauri command for the stats popover.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

/// Cumulative compression statistics.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Stats {
    /// Total number of compressions performed.
    pub total_compressions: u64,
    /// Total original tokens across all compressions.
    pub total_original_tokens: u64,
    /// Total compressed tokens across all compressions.
    pub total_compressed_tokens: u64,
    /// Total tokens saved.
    pub total_saved_tokens: u64,
    /// Compressions via accessibility API.
    pub accessibility_count: u64,
    /// Compressions via Chrome extension.
    pub extension_count: u64,
    /// Average savings percentage (rolling).
    pub avg_savings_pct: f64,
}

impl Stats {
    /// Record a compression result.
    pub fn record(
        &mut self,
        original_tokens: u64,
        compressed_tokens: u64,
        savings_pct: f64,
        from_extension: bool,
    ) {
        self.total_compressions += 1;
        self.total_original_tokens += original_tokens;
        self.total_compressed_tokens += compressed_tokens;
        self.total_saved_tokens += original_tokens.saturating_sub(compressed_tokens);

        if from_extension {
            self.extension_count += 1;
        } else {
            self.accessibility_count += 1;
        }

        // Rolling average
        if self.total_compressions == 1 {
            self.avg_savings_pct = savings_pct;
        } else {
            let n = self.total_compressions as f64;
            self.avg_savings_pct = self.avg_savings_pct * ((n - 1.0) / n) + savings_pct / n;
        }
    }

    /// Path to the stats file.
    fn path() -> PathBuf {
        dirs::home_dir()
            .expect("home dir")
            .join(".alientalk")
            .join("stats.json")
    }

    /// Load stats from disk, returning defaults on any error.
    pub fn load() -> Self {
        let path = Self::path();
        match std::fs::read_to_string(&path) {
            Ok(contents) => serde_json::from_str(&contents).unwrap_or_default(),
            Err(_) => Self::default(),
        }
    }

    /// Save stats to disk. Logs errors but doesn't fail.
    pub fn save(&self) {
        let path = Self::path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        match serde_json::to_string_pretty(self) {
            Ok(json) => {
                if let Err(e) = std::fs::write(&path, json) {
                    tracing::warn!(error = %e, "Failed to save stats");
                }
            }
            Err(e) => {
                tracing::warn!(error = %e, "Failed to serialize stats");
            }
        }
    }
}

/// Tauri command: get current stats.
#[tauri::command]
pub fn get_stats() -> Stats {
    Stats::load()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_stats_are_zero() {
        let s = Stats::default();
        assert_eq!(s.total_compressions, 0);
        assert_eq!(s.total_saved_tokens, 0);
        assert_eq!(s.avg_savings_pct, 0.0);
    }

    #[test]
    fn record_single_compression() {
        let mut s = Stats::default();
        s.record(100, 60, 40.0, false);
        assert_eq!(s.total_compressions, 1);
        assert_eq!(s.total_original_tokens, 100);
        assert_eq!(s.total_compressed_tokens, 60);
        assert_eq!(s.total_saved_tokens, 40);
        assert_eq!(s.accessibility_count, 1);
        assert_eq!(s.extension_count, 0);
        assert_eq!(s.avg_savings_pct, 40.0);
    }

    #[test]
    fn rolling_average() {
        let mut s = Stats::default();
        s.record(100, 60, 40.0, true);
        s.record(100, 80, 20.0, true);
        assert_eq!(s.total_compressions, 2);
        // Average of 40 and 20 = 30
        assert!((s.avg_savings_pct - 30.0).abs() < 0.1);
        assert_eq!(s.extension_count, 2);
    }

    #[test]
    fn record_handles_zero_savings() {
        let mut s = Stats::default();
        s.record(50, 50, 0.0, false);
        assert_eq!(s.total_saved_tokens, 0);
        assert_eq!(s.avg_savings_pct, 0.0);
    }

    #[test]
    fn serialization_roundtrip() {
        let mut s = Stats::default();
        s.record(100, 60, 40.0, false);
        let json = serde_json::to_string(&s).unwrap();
        let loaded: Stats = serde_json::from_str(&json).unwrap();
        assert_eq!(loaded.total_compressions, s.total_compressions);
        assert_eq!(loaded.total_saved_tokens, s.total_saved_tokens);
    }
}
