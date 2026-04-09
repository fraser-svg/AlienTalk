#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bridge;
mod config;
mod context;
mod pipeline;
mod queue;
mod stats;
mod tray;

use tauri::Manager;
use tracing_subscriber::{fmt, EnvFilter};

fn main() {
    // Structured logging to ~/.alientalk/daemon.log
    // No prompt text in logs (redacted)
    let log_dir = dirs::home_dir()
        .expect("home dir")
        .join(".alientalk");
    std::fs::create_dir_all(&log_dir).ok();

    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("daemon.log"))
        .expect("open log file");

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("alientalk_daemon=info"));

    fmt()
        .with_env_filter(filter)
        .with_writer(std::sync::Mutex::new(log_file))
        .json()
        .init();

    tracing::info!("AlienTalk daemon starting");

    tauri::Builder::default()
        .plugin(tauri_plugin_python::init())
        .setup(|app| {
            // Eager Python init — warm before first user request
            if let Err(e) = bridge::init_python_engine() {
                tracing::error!(error = %e, "Python engine init failed — entering degraded mode");
                bridge::set_degraded(true);
            } else {
                tracing::info!("Python engine initialized (eager)");
            }

            // System tray setup — must store handle to keep tray alive
            let tray = tray::setup_tray(app)?;
            app.manage(tray);

            // Start compression pipeline
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
        ])
        .run(tauri::generate_context!())
        .expect("error running AlienTalk daemon");
}
