#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bridge;
mod config;
mod context;
mod onboarding;
mod pipeline;
mod queue;
mod stats;
mod tray;

use tauri::Manager;
use tracing_subscriber::{fmt, EnvFilter};

fn main() {
    // Structured logging to ~/.sharp/daemon.log
    // No prompt text in logs (redacted)
    let log_dir = dirs::home_dir()
        .expect("home dir")
        .join(".sharp");
    std::fs::create_dir_all(&log_dir).ok();

    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("daemon.log"))
        .expect("open log file");

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("sharp_desktop=info"));

    fmt()
        .with_env_filter(filter)
        .with_writer(std::sync::Mutex::new(log_file))
        .json()
        .init();

    tracing::info!("Sharp daemon starting");

    tauri::Builder::default()
        .setup(|app| {
            // Initialize Sharp engine (warms regex lazy statics)
            if let Err(e) = bridge::init_engine() {
                tracing::error!(error = %e, "Engine init failed — entering degraded mode");
                bridge::set_degraded(true);
            } else {
                tracing::info!("Sharp engine ready");
            }

            // System tray setup — must store handle to keep tray alive
            let tray = tray::setup_tray(app)?;
            app.manage(tray);

            // Show onboarding on first launch
            if onboarding::should_show_onboarding() {
                let handle = app.handle().clone();
                onboarding::open_onboarding_window(&handle);
            }

            // Start optimization pipeline
            let _app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                pipeline::run(_app_handle).await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            stats::get_stats,
            config::get_config,
            config::set_config,
            onboarding::mark_onboarding_complete,
            onboarding::mark_onboarding_skipped,
            onboarding::test_compress,
        ])
        .run(tauri::generate_context!())
        .expect("error running Sharp daemon");
}
