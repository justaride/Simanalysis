//! Simanalysis Tauri desktop core. Spawns the PyInstaller `simanalysis-bridge`
//! sidecar (process-per-task), frames its stdout NDJSON, and forwards events
//! over a Channel. The webview never touches the shell directly.

use std::collections::HashMap;
use std::sync::Mutex;

use serde::Deserialize;
use serde_json::Value;
use tauri::ipc::Channel;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct ChildRegistry(Mutex<HashMap<String, CommandChild>>);

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct AnalysisOptions {
    #[serde(default)]
    quick: bool,
    #[serde(default = "default_true")]
    recursive: bool,
    #[serde(default)]
    mods_path: Option<String>,
}
fn default_true() -> bool {
    true
}

fn build_args(kind: &str, path: &str, opts: &AnalysisOptions) -> Result<Vec<String>, String> {
    let mut args: Vec<String> = Vec::new();
    match kind {
        "scan-mods" => {
            args.push("scan-mods".into());
            args.push(path.into());
            if opts.quick {
                args.push("--quick".into());
            }
            if !opts.recursive {
                args.push("--no-recursive".into());
            }
        }
        "scan-tray" => {
            args.push("scan-tray".into());
            args.push(path.into());
        }
        "analyze-save" => {
            let mods = opts
                .mods_path
                .as_deref()
                .ok_or("analyze-save requires options.modsPath")?;
            args.push("analyze-save".into());
            args.push(path.into());
            args.push(mods.into());
        }
        other => return Err(format!("unknown analysis kind: {other}")),
    }
    Ok(args)
}

fn drain_complete_lines(buf: &mut Vec<u8>) -> Vec<Vec<u8>> {
    let mut out = Vec::new();
    while let Some(nl) = buf.iter().position(|&b| b == b'\n') {
        let line: Vec<u8> = buf.drain(..=nl).collect();
        out.push(line[..line.len() - 1].to_vec());
    }
    out
}

fn forward_line(on_event: &Channel<Value>, line: &[u8]) -> bool {
    let text = match std::str::from_utf8(line) {
        Ok(t) => t.trim(),
        Err(_) => return false,
    };
    if text.is_empty() {
        return false;
    }
    match serde_json::from_str::<Value>(text) {
        Ok(value) => {
            let is_result = value.get("type").and_then(|t| t.as_str()) == Some("result");
            let _ = on_event.send(value);
            is_result
        }
        Err(e) => {
            eprintln!("dropping non-JSON stdout line: {e}: {text}");
            false
        }
    }
}

#[tauri::command]
async fn start_analysis(
    app: AppHandle,
    task_id: String,
    kind: String,
    path: String,
    options: AnalysisOptions,
    on_event: Channel<Value>,
) -> Result<(), String> {
    let args = build_args(&kind, &path, &options)?;
    let sidecar = app
        .shell()
        .sidecar("simanalysis-bridge")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(args);
    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    app.state::<ChildRegistry>()
        .0
        .lock()
        .unwrap()
        .insert(task_id.clone(), child);

    let reader_app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buf: Vec<u8> = Vec::new();
        let mut saw_result = false;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    buf.extend_from_slice(&bytes);
                    for line in drain_complete_lines(&mut buf) {
                        if forward_line(&on_event, &line) {
                            saw_result = true;
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    if let Ok(text) = std::str::from_utf8(&bytes) {
                        let t = text.trim_end();
                        if !t.is_empty() {
                            eprintln!("[bridge:{task_id}] {t}");
                        }
                    }
                }
                CommandEvent::Error(err) => {
                    let _ = on_event.send(serde_json::json!({
                        "v": 1, "type": "error", "code": "IO_ERROR", "message": err
                    }));
                }
                CommandEvent::Terminated(payload) => {
                    if !buf.is_empty() {
                        if forward_line(&on_event, &buf) {
                            saw_result = true;
                        }
                        buf.clear();
                    }
                    let code = payload.code.unwrap_or(-1);
                    if code != 0 && !saw_result {
                        let _ = on_event.send(serde_json::json!({
                            "v": 1, "type": "error", "code": "CRASHED",
                            "message": format!("analyzer exited with code {code}; see logs")
                        }));
                    }
                    break;
                }
                _ => {}
            }
        }
        reader_app
            .state::<ChildRegistry>()
            .0
            .lock()
            .unwrap()
            .remove(&task_id);
    });

    Ok(())
}

#[tauri::command]
fn cancel_analysis(app: AppHandle, task_id: String) -> Result<(), String> {
    if let Some(child) = app.state::<ChildRegistry>().0.lock().unwrap().remove(&task_id) {
        child
            .kill()
            .map_err(|e| format!("failed to kill task {task_id}: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
fn health() -> Value {
    serde_json::json!({ "status": "ok", "version": env!("CARGO_PKG_VERSION") })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(ChildRegistry::default())
        .invoke_handler(tauri::generate_handler![start_analysis, cancel_analysis, health])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::drain_complete_lines;

    #[test]
    fn frames_lines_across_chunk_boundaries() {
        let mut buf = Vec::new();
        buf.extend_from_slice(b"{\"a\":1}\n{\"b\"");
        let lines = drain_complete_lines(&mut buf);
        assert_eq!(lines, vec![b"{\"a\":1}".to_vec()]);
        assert_eq!(buf, b"{\"b\"".to_vec());
        buf.extend_from_slice(b":2}\n");
        let lines = drain_complete_lines(&mut buf);
        assert_eq!(lines, vec![b"{\"b\":2}".to_vec()]);
        assert!(buf.is_empty());
    }

    #[test]
    fn no_complete_line_keeps_buffer() {
        let mut buf = b"partial".to_vec();
        assert!(drain_complete_lines(&mut buf).is_empty());
        assert_eq!(buf, b"partial".to_vec());
    }
}
