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
    // 1. Check runtime token in production data directory
    if let Ok(app_dir) = app.path().app_data_dir() {
        let token_path = app_dir.join("data").join(".aiwa_session_token");
        if let Ok(token) = fs::read_to_string(&token_path) {
            return Ok(token.trim().to_string());
        }
    }

    // 2. Check local working directory
    let local_token = PathBuf::from("data/.aiwa_session_token");
    if let Ok(token) = fs::read_to_string(&local_token) {
        return Ok(token.trim().to_string());
    }

    // 3. Check development relative path
    let dev_token = PathBuf::from("../../data/.aiwa_session_token");
    if let Ok(token) = fs::read_to_string(&dev_token) {
        return Ok(token.trim().to_string());
    }

    Err("Active session token not ready yet".into())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![get_session_token])
        .setup(|app| {
            // Spawn the folder-based sidecar launcher
            println!("[AIWA Desktop] Launching backend folder-based sidecar...");
            let sidecar_command = app.shell().sidecar("aiwa-backend");

            if let Ok(cmd) = sidecar_command {
                match cmd.spawn() {
                    Ok((_rx, child)) => {
                        let state = app.state::<BackendProcess>();
                        *state.0.lock().unwrap() = Some(child);
                        println!("[AIWA Desktop] ✅ Backend sidecar spawned successfully.");
                    }
                    Err(e) => {
                        eprintln!("[AIWA Desktop] ⚠️ Failed spawning sidecar: {}", e);
                    }
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Error while building AIWA desktop application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                // Terminate sidecar process on app exit so no orphan processes linger
                let state = app_handle.state::<BackendProcess>();
                if let Some(child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                    println!("[AIWA Desktop] Backend sidecar terminated cleanly.");
                }
            }
        });
}
