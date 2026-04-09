//! System tray — menu bar icon and popover.

use tauri::{
    menu::{Menu, MenuItemBuilder, PredefinedMenuItem},
    tray::TrayIconBuilder,
};

use crate::bridge;
use crate::stats::Stats;

/// Set up the system tray icon and menu.
/// Returns the TrayIcon handle — caller must keep it alive.
pub fn setup_tray(app: &tauri::App) -> Result<tauri::tray::TrayIcon, Box<dyn std::error::Error>> {
    let stats = Stats::load();

    let stats_label = format!(
        "Saved {} tokens ({:.0}% avg)",
        stats.total_saved_tokens, stats.avg_savings_pct
    );

    let status = if bridge::is_degraded() {
        "Status: Engine Offline"
    } else {
        "Status: Active"
    };

    let menu = Menu::with_items(
        app,
        &[
            &MenuItemBuilder::new("AlienTalk").enabled(false).build(app)?,
            &MenuItemBuilder::new(status).enabled(false).build(app)?,
            &MenuItemBuilder::new(&stats_label).enabled(false).build(app)?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItemBuilder::with_id("settings", "Settings...").build(app)?,
            &MenuItemBuilder::with_id("quit", "Quit")
                .accelerator("CmdOrCtrl+Q")
                .build(app)?,
        ],
    )?;

    let tray = TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("AlienTalk — Prompt Intelligence")
        .on_menu_event(|app, event| {
            match event.id().as_ref() {
                "quit" => {
                    tracing::info!("Quit requested from tray");
                    app.exit(0);
                }
                "settings" => {
                    tracing::info!("Settings requested from tray");
                    // TODO: Open settings window
                }
                _ => {}
            }
        })
        .build(app)?;

    Ok(tray)
}
