// apps/desktop/src-tauri/src/main.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, RunEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

struct BackendProcess(Mutex<Option<CommandChild>>);

#[tauri::command]
fn get_session_token(app: AppHandle) -> Result<String, String> {
    // Locate the token written by the FastAPI startup lifespan
    let base_path = app.path().app_data_dir().unwrap_or(PathBuf::from("."));
    let token_path = base_path.join("data").join(".aiwa_session_token");

    // Fallback to relative path during local desktop development
    let dev_token_path = PathBuf::from("../../data/.aiwa_session_token");

    if let Ok(token) = fs::read_to_string(&token_path) {
        return Ok(token.trim().to_string());
    } else if let Ok(token) = fs::read_to_string(&dev_token_path) {
        return Ok(token.trim().to_string());
    }

    Err("Session token not found or backend not ready".into())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![get_session_token])
        .setup(|app| {
            // Spawn the FastAPI backend sidecar
            let sidecar_command = app.shell().sidecar("aiwa-backend");
            if let Ok(cmd) = sidecar_command {
                if let Ok((_rx, child)) = cmd.spawn() {
                    let state = app.state::<BackendProcess>();
                    *state.0.lock().unwrap() = Some(child);
                    println!("[Tauri] aiwa-backend sidecar spawned successfully.");
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                // Terminate the sidecar child process so no orphan daemon remains
                let state = app_handle.state::<BackendProcess>();
                if let Some(child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                    println!("[Tauri] aiwa-backend sidecar stopped.");
                }
            }
        });
}
