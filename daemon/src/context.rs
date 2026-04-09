//! Context detection — maps app bundle IDs to compression modes.
//!
//! Different apps benefit from different compression intensities:
//! - Code editors: lighter compression (preserve technical terms)
//! - Chat/browser: full compression
//! - Terminal: moderate (protect commands)

/// Compression mode based on application context.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CompressionMode {
    /// Full compression — chat interfaces, browsers
    Full,
    /// Moderate — terminals, general text
    Moderate,
    /// Light — code editors (preserve technical precision)
    Light,
    /// Skip — app is in the blacklist
    Blocked,
}

/// App blacklist — never compress in these apps.
const BLOCKED_APPS: &[&str] = &[
    "com.1password.1password",
    "com.agilebits.onepassword7",
    "com.lastpass.LastPass",
    "com.bitwarden.desktop",
    "com.apple.keychainaccess",
    // Banking apps are caught by generic patterns below
];

/// Detect compression mode from app bundle ID.
pub fn detect_mode(bundle_id: &str) -> CompressionMode {
    // Check blacklist first
    if BLOCKED_APPS.contains(&bundle_id) {
        return CompressionMode::Blocked;
    }

    // Block banking/financial apps by pattern
    let lower = bundle_id.to_lowercase();
    if lower.contains("bank") || lower.contains("finance") || lower.contains("trading") {
        return CompressionMode::Blocked;
    }

    // Code editors — light compression
    if matches!(
        bundle_id,
        "com.microsoft.VSCode"
            | "com.todesktop.230313mzl4w4u92"  // Cursor
            | "dev.zed.Zed"
            | "com.sublimetext.4"
            | "com.jetbrains.intellij"
            | "com.jetbrains.pycharm"
            | "com.jetbrains.WebStorm"
            | "com.jetbrains.goland"
            | "com.apple.dt.Xcode"
    ) {
        return CompressionMode::Light;
    }

    // Terminals — moderate compression
    if matches!(
        bundle_id,
        "com.apple.Terminal"
            | "com.googlecode.iterm2"
            | "dev.warp.Warp-Stable"
            | "io.alacritty"
            | "com.mitchellh.ghostty"
    ) {
        return CompressionMode::Moderate;
    }

    // Everything else — full compression
    CompressionMode::Full
}

/// Convert mode to compression intensity (0.0-1.0).
pub fn mode_to_intensity(mode: CompressionMode) -> f64 {
    match mode {
        CompressionMode::Full => 1.0,
        CompressionMode::Moderate => 0.7,
        CompressionMode::Light => 0.4,
        CompressionMode::Blocked => 0.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn password_managers_blocked() {
        assert_eq!(detect_mode("com.1password.1password"), CompressionMode::Blocked);
        assert_eq!(detect_mode("com.bitwarden.desktop"), CompressionMode::Blocked);
    }

    #[test]
    fn banking_apps_blocked_by_pattern() {
        assert_eq!(detect_mode("com.chase.mobilebanking"), CompressionMode::Blocked);
        assert_eq!(detect_mode("com.schwab.trading"), CompressionMode::Blocked);
    }

    #[test]
    fn code_editors_light() {
        assert_eq!(detect_mode("com.microsoft.VSCode"), CompressionMode::Light);
        assert_eq!(detect_mode("dev.zed.Zed"), CompressionMode::Light);
    }

    #[test]
    fn terminals_moderate() {
        assert_eq!(detect_mode("com.apple.Terminal"), CompressionMode::Moderate);
        assert_eq!(detect_mode("dev.warp.Warp-Stable"), CompressionMode::Moderate);
    }

    #[test]
    fn unknown_apps_full() {
        assert_eq!(detect_mode("com.example.unknown"), CompressionMode::Full);
        assert_eq!(detect_mode("org.chromium.Chromium"), CompressionMode::Full);
    }

    #[test]
    fn mode_intensities() {
        assert_eq!(mode_to_intensity(CompressionMode::Full), 1.0);
        assert_eq!(mode_to_intensity(CompressionMode::Moderate), 0.7);
        assert_eq!(mode_to_intensity(CompressionMode::Light), 0.4);
        assert_eq!(mode_to_intensity(CompressionMode::Blocked), 0.0);
    }
}
