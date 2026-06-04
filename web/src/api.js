// Tauri-backed transport. Drop-in replacement for the old WebSocket client:
// public functions and callback shape are unchanged, so the React views keep
// calling api.scanMods(path, { onProgress, onComplete, ... }) as before.
import { invoke, Channel } from '@tauri-apps/api/core';

const TREATMENT_OUTCOMES = new Set(['same_issue', 'issue_gone', 'different_issue']);
const TREATMENT_RESTORE_STEPS = new Set(['latest', 'all']);

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
        callbacks?.onResult?.(msg.data);
        callbacks?.onComplete?.(msg.data);
        break;
      case 'done':
        callbacks?.onDone?.();
        break;
      case 'error':
        callbacks?.onError?.(msg.message ?? 'Analysis failed');
        break;
    }
  };

  invoke('start_analysis', { taskId, kind, path, options, onEvent: channel })
    .catch((e) => callbacks?.onError?.(String(e)));

  const cancel = () => invoke('cancel_analysis', { taskId }).catch(() => {});
  return { taskId, cancel, close: cancel };
}

function treatmentPlanOptions(modsPath, optionsOrSave) {
  if (typeof optionsOrSave === 'object' && optionsOrSave !== null) {
    return {
      modsPath,
      save: Boolean(optionsOrSave.save),
      doctorJsonPath: optionsOrSave.doctorJsonPath,
    };
  }
  return { modsPath, save: Boolean(optionsOrSave) };
}

function validateTreatmentOutcome(outcome) {
  if (!TREATMENT_OUTCOMES.has(outcome)) {
    throw new Error(`Unsupported treatment outcome: ${outcome}`);
  }
}

function validateTreatmentRestoreStep(step) {
  if (step != null && !TREATMENT_RESTORE_STEPS.has(step)) {
    throw new Error(`Unsupported treatment restore step: ${step}`);
  }
}

export const api = {
  health: () => invoke('health'),
  scanMods: (path, callbacks) =>
    runAnalysis('scan-mods', path, { quick: false, recursive: true }, callbacks),
  scanTray: (path, callbacks) =>
    runAnalysis('scan-tray', path, {}, callbacks),
  analyzeSave: (savePath, modsPath, callbacks) =>
    runAnalysis('analyze-save', savePath, { modsPath }, callbacks),
  scanDoctor: (sims4Path, modsPath, callbacks) =>
    runAnalysis('doctor-scan', sims4Path, { modsPath, recursive: false }, callbacks),
  scanWorld: (sims4Path, callbacks) =>
    runAnalysis('world-scan', sims4Path, {}, callbacks),
  worldStatus: (sims4Path, callbacks) =>
    runAnalysis('world-status', sims4Path, {}, callbacks),
  planFixes: (sims4Path, callbacks) =>
    runAnalysis('fix-plan', sims4Path, {}, callbacks),
  fixStatus: (sims4Path, callbacks) =>
    runAnalysis('fix-status', sims4Path, {}, callbacks),
  applyFix: (sims4Path, kind, callbacks) =>
    runAnalysis('fix-apply', sims4Path, { kind }, callbacks),
  restoreFix: (manifestPath, callbacks) =>
    runAnalysis('fix-restore', manifestPath, {}, callbacks),
  fixSessionStatus: (manifestPath, callbacks) =>
    runAnalysis('fix-session-status', manifestPath, {}, callbacks),
  planMaster: (sims4Path, callbacks) =>
    runAnalysis('master-plan', sims4Path, {}, callbacks),
  masterStatus: (sims4Path, callbacks) =>
    runAnalysis('master-status', sims4Path, {}, callbacks),
  saveMasterBaseline: (sims4Path, label, callbacks) =>
    runAnalysis('master-baseline-save', sims4Path, { label }, callbacks),
  diffMasterBaseline: (sims4Path, baselinePath, callbacks) =>
    runAnalysis('master-baseline-diff', sims4Path, { baselinePath }, callbacks),
  masterBaselineStatus: (sims4Path, callbacks) =>
    runAnalysis('master-baseline-status', sims4Path, {}, callbacks),
  monitorLive: (sims4Path, modsPath, interval, callbacks) =>
    runAnalysis(
      'live-monitor',
      sims4Path,
      { modsPath, interval, once: false },
      callbacks,
    ),
  planTreatment: (sims4Path, modsPath, save, callbacks) =>
    runAnalysis(
      'treatment-plan',
      sims4Path,
      treatmentPlanOptions(modsPath, save),
      callbacks,
    ),
  applyTreatment: (manifestPath, callbacks) =>
    runAnalysis('treatment-apply', manifestPath, {}, callbacks),
  recordTreatmentOutcome: (manifestPath, outcome, callbacks) => {
    validateTreatmentOutcome(outcome);
    return runAnalysis('treatment-outcome', manifestPath, { outcome }, callbacks);
  },
  restoreTreatment: (manifestPath, step, callbacks) => {
    validateTreatmentRestoreStep(step);
    return runAnalysis('treatment-restore', manifestPath, { step }, callbacks);
  },
  treatmentStatus: (manifestPath, callbacks) =>
    runAnalysis('treatment-status', manifestPath, {}, callbacks),
};

export default api;
