// Tauri-backed transport. Drop-in replacement for the old WebSocket client:
// public functions and callback shape are unchanged, so the React views keep
// calling api.scanMods(path, { onProgress, onComplete, ... }) as before.
import { invoke, Channel } from '@tauri-apps/api/core';

function runAnalysis(kind, path, options, callbacks) {
  const taskId = crypto.randomUUID();
  const channel = new Channel();

  channel.onmessage = (msg) => {
    switch (msg.type) {
      case 'start':
        callbacks?.onStart?.();
        break;
      case 'progress':
        callbacks?.onProgress?.({
          current: msg.current,
          total: msg.total,
          file: msg.file,
          stage: msg.stage,
        });
        break;
      case 'result':
        callbacks?.onComplete?.(msg.data);
        break;
      case 'error':
        callbacks?.onError?.(msg.message ?? 'Analysis failed');
        break;
      // 'done': completion is signalled by 'result'; no extra UI action.
    }
  };

  invoke('start_analysis', { taskId, kind, path, options, onEvent: channel })
    .catch((e) => callbacks?.onError?.(String(e)));

  const cancel = () => invoke('cancel_analysis', { taskId }).catch(() => {});
  return { taskId, cancel, close: cancel };
}

export const api = {
  health: () => invoke('health'),
  scanMods: (path, callbacks) =>
    runAnalysis('scan-mods', path, { quick: false, recursive: true }, callbacks),
  scanTray: (path, callbacks) =>
    runAnalysis('scan-tray', path, {}, callbacks),
  analyzeSave: (savePath, modsPath, callbacks) =>
    runAnalysis('analyze-save', savePath, { modsPath }, callbacks),
};

export default api;
