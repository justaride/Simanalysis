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

#[derive(Default)]
struct ThumbnailCache(Mutex<HashMap<String, Option<String>>>);

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

// ── Config dir helper ────────────────────────────────────────────────────────

fn simanalysis_config_dir() -> Result<std::path::PathBuf, String> {
    let home = dirs::home_dir().ok_or_else(|| "cannot determine home directory".to_string())?;
    Ok(home.join(".simanalysis"))
}

fn config_file_path() -> Result<std::path::PathBuf, String> {
    Ok(simanalysis_config_dir()?.join("config.json"))
}

// ── get_config ───────────────────────────────────────────────────────────────

/// Read ~/.simanalysis/config.json and return it.
/// If the file is absent, returns the default shape: {"last_scan_path": null}.
#[tauri::command]
fn get_config() -> Value {
    match config_file_path() {
        Err(_) => serde_json::json!({ "last_scan_path": null }),
        Ok(path) => {
            if !path.exists() {
                return serde_json::json!({ "last_scan_path": null });
            }
            match std::fs::read_to_string(&path) {
                Ok(contents) => serde_json::from_str::<Value>(&contents)
                    .unwrap_or_else(|_| serde_json::json!({ "last_scan_path": null })),
                Err(_) => serde_json::json!({ "last_scan_path": null }),
            }
        }
    }
}

// ── set_config ───────────────────────────────────────────────────────────────

/// Shallow-merge `patch` into ~/.simanalysis/config.json (creating it if absent).
/// Returns {"status":"ok"}.
#[tauri::command]
fn set_config(patch: Value) -> Result<Value, String> {
    let config_dir = simanalysis_config_dir()?;
    let config_path = config_dir.join("config.json");

    std::fs::create_dir_all(&config_dir)
        .map_err(|e| format!("cannot create config dir: {e}"))?;

    // Load existing config (or start with {})
    let mut existing: serde_json::Map<String, Value> = if config_path.exists() {
        match std::fs::read_to_string(&config_path) {
            Ok(s) => serde_json::from_str::<Value>(&s)
                .ok()
                .and_then(|v| v.as_object().cloned())
                .unwrap_or_default(),
            Err(_) => Default::default(),
        }
    } else {
        Default::default()
    };

    // Shallow-merge patch
    if let Some(patch_obj) = patch.as_object() {
        for (k, v) in patch_obj {
            existing.insert(k.clone(), v.clone());
        }
    }

    let serialized = serde_json::to_string_pretty(&Value::Object(existing))
        .map_err(|e| format!("serialization error: {e}"))?;

    std::fs::write(&config_path, serialized)
        .map_err(|e| format!("cannot write config: {e}"))?;

    Ok(serde_json::json!({ "status": "ok" }))
}

// ── delete_mod_file ──────────────────────────────────────────────────────────

/// Move a mod file to the OS trash with safety checks and audit logging.
/// Returns {"status":"ok","moved_to_trash":true,"message":"..."}.
#[tauri::command]
fn delete_mod_file(path: String) -> Result<Value, String> {
    use std::time::{SystemTime, UNIX_EPOCH};

    let file_path = std::path::Path::new(&path)
        .canonicalize()
        .map_err(|e| format!("cannot resolve path '{path}': {e}"))?;

    if !file_path.exists() {
        return Err(format!("File not found: {path}"));
    }
    if !file_path.is_file() {
        return Err(format!("Path is not a file: {path}"));
    }
    let suffix = file_path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_ascii_lowercase())
        .unwrap_or_default();
    if suffix != "package" && suffix != "ts4script" {
        return Err(format!("Not a valid mod file (suffix '.{suffix}' not allowed)"));
    }

    // Audit log
    let config_dir = simanalysis_config_dir()?;
    std::fs::create_dir_all(&config_dir)
        .map_err(|e| format!("cannot create config dir: {e}"))?;
    let log_path = config_dir.join("deletion_log.txt");

    let unix_secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Format as a simple RFC-3339-ish UTC timestamp without chrono dependency
    let timestamp = format_unix_timestamp(unix_secs);
    let log_line = format!("{timestamp} | DELETED | {}\n", file_path.display());

    // Append (best-effort; don't fail the delete if the log write fails)
    let _ = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .and_then(|mut f| std::io::Write::write_all(&mut f, log_line.as_bytes()));

    // Move to trash
    trash::delete(&file_path).map_err(|e| format!("failed to move to trash: {e}"))?;

    let msg = format!("File moved to trash: {}", file_path.display());
    Ok(serde_json::json!({
        "status": "ok",
        "moved_to_trash": true,
        "message": msg
    }))
}

/// Format a Unix timestamp (seconds since epoch) as "YYYY-MM-DDTHH:MM:SSZ".
fn format_unix_timestamp(secs: u64) -> String {
    // Days since epoch
    let s = secs % 60;
    let m = (secs / 60) % 60;
    let h = (secs / 3600) % 24;
    let days = secs / 86400;

    // Gregorian calendar calculation (simple but correct for modern dates)
    let (year, month, day) = days_to_ymd(days);
    format!("{year:04}-{month:02}-{day:02}T{h:02}:{m:02}:{s:02}Z")
}

fn days_to_ymd(days: u64) -> (u64, u64, u64) {
    // Civil calendar conversion — Fliegel & Van Flandern algorithm adapted for epoch
    let z = days + 719468;
    let era = z / 146097;
    let doe = z % 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

// ── get_thumbnail ─────────────────────────────────────────────────────────────

/// Fetch a thumbnail for the given .package path via the sidecar.
/// Returns `Some("data:image/png;base64,...")` on success, `None` if no thumbnail,
/// or `Err(...)` on spawn/parse failure. Results are cached per-path.
#[tauri::command]
async fn get_thumbnail(
    app: AppHandle,
    path: String,
    cache: tauri::State<'_, ThumbnailCache>,
) -> Result<Option<String>, String> {
    // Check cache first — hold the lock only briefly, no await while locked.
    {
        let guard = cache.0.lock().unwrap();
        if let Some(cached) = guard.get(&path) {
            return Ok(cached.clone());
        }
    }

    // Spawn the sidecar one-shot and collect all stdout.
    let sidecar = app
        .shell()
        .sidecar("simanalysis-bridge")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(["thumbnail", &path]);

    let (mut rx, _child) = sidecar
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    let mut stdout_buf: Vec<u8> = Vec::new();
    let mut result_value: Option<Value> = None;

    loop {
        match rx.recv().await {
            Some(CommandEvent::Stdout(bytes)) => {
                stdout_buf.extend_from_slice(&bytes);
            }
            Some(CommandEvent::Stderr(bytes)) => {
                if let Ok(text) = std::str::from_utf8(&bytes) {
                    let t = text.trim_end();
                    if !t.is_empty() {
                        eprintln!("[thumbnail] {t}");
                    }
                }
            }
            Some(CommandEvent::Terminated(_)) | None => {
                break;
            }
            _ => {}
        }
    }

    // Parse all complete NDJSON lines and find the "result" event.
    for line in std::str::from_utf8(&stdout_buf)
        .unwrap_or("")
        .lines()
        .filter(|l| !l.trim().is_empty())
    {
        if let Ok(v) = serde_json::from_str::<Value>(line) {
            if v.get("type").and_then(|t| t.as_str()) == Some("result") {
                result_value = Some(v);
                break;
            }
        }
    }

    let url = match result_value {
        Some(v) => {
            let data = &v["data"];
            if data["found"].as_bool().unwrap_or(false) {
                data["b64"]
                    .as_str()
                    .map(|b| format!("data:image/png;base64,{b}"))
            } else {
                None
            }
        }
        None => None,
    };

    // Store in cache (no await held, just a short lock).
    {
        let mut guard = cache.0.lock().unwrap();
        guard.insert(path, url.clone());
    }

    Ok(url)
}

// ── check_updates ────────────────────────────────────────────────────────────

/// Stub: always reports no update available.
/// Returns null (JSON null) so Layout.jsx's `if (update)` guard suppresses the banner.
#[tauri::command]
fn check_updates() -> Value {
    Value::Null
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(ChildRegistry::default())
        .manage(ThumbnailCache::default())
        .invoke_handler(tauri::generate_handler![
            start_analysis,
            cancel_analysis,
            health,
            get_config,
            set_config,
            delete_mod_file,
            check_updates,
            get_thumbnail
        ])
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
