//! Settings manager — persists user configuration.
//!
//! Stored at ~/.sharp/config.json.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::onboarding::OnboardingState;

/// User-configurable settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Global hotkey (default: Cmd+Shift+Enter)
    pub hotkey: String,
    /// Whether the daemon is enabled (can be toggled from menu bar).
    pub enabled: bool,
    /// Apps to always compress in (allowlist for AX API).
    pub allowed_apps: Vec<String>,
    /// Whether "enable everywhere" mode is on.
    pub enable_everywhere: bool,
    /// Whether to show toast notifications.
    pub show_toasts: bool,
    /// Onboarding flow state.
    #[serde(default)]
    pub onboarding_state: OnboardingState,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            hotkey: "Cmd+Shift+Enter".to_string(),
            enabled: true,
            allowed_apps: vec![
                "com.apple.Terminal".to_string(),
                "com.googlecode.iterm2".to_string(),
                "dev.warp.Warp-Stable".to_string(),
                "com.microsoft.VSCode".to_string(),
                "com.todesktop.230313mzl4w4u92".to_string(), // Cursor
            ],
            enable_everywhere: false,
            show_toasts: true,
            onboarding_state: OnboardingState::default(),
        }
    }
}

impl Config {
    fn path() -> PathBuf {
        dirs::home_dir()
            .expect("home dir")
            .join(".sharp")
            .join("config.json")
    }

    pub fn load() -> Self {
        let path = Self::path();
        match std::fs::read_to_string(&path) {
            Ok(contents) => match serde_json::from_str(&contents) {
                Ok(config) => config,
                Err(e) => {
                    tracing::warn!(error = %e, "Config file corrupt — using defaults");
                    Self::default()
                }
            },
            Err(_) => Self::default(),
        }
    }

    pub fn save(&self) {
        let path = Self::path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        match serde_json::to_string_pretty(self) {
            Ok(json) => {
                if let Err(e) = std::fs::write(&path, json) {
                    tracing::warn!(error = %e, "Failed to save config");
                }
            }
            Err(e) => {
                tracing::warn!(error = %e, "Failed to serialize config");
            }
        }
    }

    /// Check if an app is allowed for compression.
    pub fn is_app_allowed(&self, bundle_id: &str) -> bool {
        if self.enable_everywhere {
            return true;
        }
        self.allowed_apps.iter().any(|a| a == bundle_id)
    }
}

/// Tauri command: get current config.
#[tauri::command]
pub fn get_config() -> Config {
    Config::load()
}

/// Tauri command: update config.
/// Validates inputs before persisting to prevent escalation via IPC.
#[tauri::command]
pub fn set_config(config: Config) -> Result<(), String> {
    // Validate hotkey format (modifier+key only)
    let valid_modifiers = ["Cmd", "Ctrl", "Alt", "Shift", "CmdOrCtrl"];
    for part in config.hotkey.split('+') {
        let trimmed = part.trim();
        if !valid_modifiers.contains(&trimmed) && trimmed.len() > 1 {
            // Single character keys are fine, multi-char must be a modifier
            if !trimmed.chars().all(|c| c.is_ascii_alphanumeric()) {
                return Err(format!("Invalid hotkey component: {trimmed}"));
            }
        }
    }

    // Validate allowed_apps contains only plausible bundle IDs
    for app_id in &config.allowed_apps {
        if !app_id.contains('.') || app_id.len() > 256 {
            return Err(format!("Invalid bundle ID: {app_id}"));
        }
    }

    config.save();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_has_dev_tools() {
        let c = Config::default();
        assert!(c.is_app_allowed("com.apple.Terminal"));
        assert!(c.is_app_allowed("com.microsoft.VSCode"));
        assert!(!c.is_app_allowed("com.random.app"));
    }

    #[test]
    fn enable_everywhere_allows_all() {
        let mut c = Config::default();
        c.enable_everywhere = true;
        assert!(c.is_app_allowed("com.random.app"));
        assert!(c.is_app_allowed("anything"));
    }

    #[test]
    fn serialization_roundtrip() {
        let c = Config::default();
        let json = serde_json::to_string(&c).unwrap();
        let loaded: Config = serde_json::from_str(&json).unwrap();
        assert_eq!(loaded.hotkey, c.hotkey);
        assert_eq!(loaded.allowed_apps.len(), c.allowed_apps.len());
    }
}
