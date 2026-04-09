//! Onboarding state machine — guides new users through first-launch setup.
//!
//! States: NotStarted → Welcome → ExtensionInstall → TestCompress → Complete
//!         (any state can transition to Skipped)
//!
//! Persisted in ~/.alientalk/config.json via the `onboarding_state` field.

use serde::{Deserialize, Serialize};

use crate::config::Config;

/// Onboarding progress states.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OnboardingState {
    NotStarted,
    Welcome,
    ExtensionInstall,
    TestCompress,
    Complete,
    Skipped,
}

impl Default for OnboardingState {
    fn default() -> Self {
        Self::NotStarted
    }
}

impl OnboardingState {
    /// Parse from config string, defaulting to NotStarted.
    pub fn from_str_loose(s: &str) -> Self {
        match s {
            "not_started" => Self::NotStarted,
            "welcome" => Self::Welcome,
            "extension_install" => Self::ExtensionInstall,
            "test_compress" => Self::TestCompress,
            "complete" => Self::Complete,
            "skipped" => Self::Skipped,
            _ => Self::NotStarted,
        }
    }
}

/// Check whether the onboarding window should be shown.
///
/// Returns true if onboarding has never been completed or skipped.
pub fn should_show_onboarding() -> bool {
    let config = Config::load();
    matches!(
        config.onboarding_state,
        OnboardingState::NotStarted
            | OnboardingState::Welcome
            | OnboardingState::ExtensionInstall
            | OnboardingState::TestCompress
    )
}

/// Mark onboarding as complete and persist to config.
pub fn mark_complete() {
    let mut config = Config::load();
    config.onboarding_state = OnboardingState::Complete;
    config.save();
    tracing::info!("Onboarding marked complete");
}

/// Mark onboarding as skipped and persist to config.
pub fn mark_skipped() {
    let mut config = Config::load();
    config.onboarding_state = OnboardingState::Skipped;
    config.save();
    tracing::info!("Onboarding skipped by user");
}

/// Tauri command: mark onboarding complete (called from webview).
#[tauri::command]
pub fn mark_onboarding_complete() {
    mark_complete();
}

/// Tauri command: mark onboarding skipped (called from webview).
#[tauri::command]
pub fn mark_onboarding_skipped() {
    mark_skipped();
}

/// Maximum input size for test compression (same as bridge).
const MAX_TEST_INPUT: usize = 64 * 1024;

/// Tauri command: test compression (called from onboarding step 3).
#[tauri::command]
pub fn test_compress(text: String) -> String {
    if text.trim().is_empty() {
        return String::new();
    }
    if text.len() > MAX_TEST_INPUT {
        return text;
    }
    crate::engine::compile(&text)
}

/// Open the onboarding webview window.
///
/// If a window with label "onboarding" already exists, focus it instead.
pub fn open_onboarding_window(app: &tauri::AppHandle) {
    use tauri::Manager;

    // If window already exists, just focus it
    if let Some(window) = app.get_webview_window("onboarding") {
        window.set_focus().ok();
        return;
    }

    let builder = tauri::WebviewWindowBuilder::new(
        app,
        "onboarding",
        tauri::WebviewUrl::App("onboarding/index.html".into()),
    )
    .title("AlienTalk Setup")
    .inner_size(560.0, 520.0)
    .resizable(false)
    .center()
    .visible(true);

    match builder.build() {
        Ok(_) => tracing::info!("Onboarding window opened"),
        Err(e) => tracing::error!(error = %e, "Failed to open onboarding window"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_state_is_not_started() {
        assert_eq!(OnboardingState::default(), OnboardingState::NotStarted);
    }

    #[test]
    fn from_str_loose_parses_known_states() {
        assert_eq!(
            OnboardingState::from_str_loose("complete"),
            OnboardingState::Complete
        );
        assert_eq!(
            OnboardingState::from_str_loose("skipped"),
            OnboardingState::Skipped
        );
        assert_eq!(
            OnboardingState::from_str_loose("not_started"),
            OnboardingState::NotStarted
        );
    }

    #[test]
    fn from_str_loose_defaults_on_garbage() {
        assert_eq!(
            OnboardingState::from_str_loose("garbage"),
            OnboardingState::NotStarted
        );
    }

    #[test]
    fn serialization_roundtrip() {
        let state = OnboardingState::Complete;
        let json = serde_json::to_string(&state).unwrap();
        assert_eq!(json, "\"complete\"");
        let parsed: OnboardingState = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, OnboardingState::Complete);
    }

    #[test]
    fn test_compress_empty_input() {
        let result = test_compress(String::new());
        assert_eq!(result, "");
    }

    #[test]
    fn test_compress_returns_compressed() {
        let result = test_compress("I want you to explain how databases work".to_string());
        assert!(!result.contains("I want you to"));
        assert!(result.contains("explain"));
    }
}
