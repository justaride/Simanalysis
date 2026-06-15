export function hasTauriInvoke(target = globalThis) {
    return typeof target?.__TAURI_INTERNALS__?.invoke === 'function';
}
