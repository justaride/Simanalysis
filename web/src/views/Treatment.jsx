import { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
    AlertTriangle,
    CheckCircle,
    Copy,
    Download,
    FileText,
    FolderOpen,
    Loader2,
    Play,
    RotateCcw,
    ShieldCheck,
    Stethoscope,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import {
    canRequestTreatmentHandoff,
    summarizeTreatmentHandoff,
    treatmentHandoffFilename,
} from './treatmentModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

const OUTCOME_OPTIONS = [
    { value: 'same_issue', label: 'Same Issue' },
    { value: 'issue_gone', label: 'Issue Gone' },
    { value: 'different_issue', label: 'Different Issue' },
];

const OUTCOME_CONFIRMATIONS = {
    same_issue:
        'Record Same Issue? Simanalysis will restore the currently removed batch, then narrow the plan to the remaining candidates.',
    issue_gone:
        'Record Issue Gone? Simanalysis will keep this removed batch out and may restore older removed batches while narrowing the plan.',
    different_issue:
        'Record Different Issue? Simanalysis will stop automatic narrowing and mark this session for manual review.',
};

const MUTATING_ACTIONS = new Set(['apply', 'outcome', 'restore']);

function statusLabel(status) {
    return status ? status.replaceAll('_', ' ') : 'No plan';
}

function unitName(path) {
    const parts = String(path || '').split('/');
    return parts[parts.length - 1] || path;
}

function StatTile({ label, value, tone = 'gray' }) {
    const tones = {
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
        green: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-200',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-2 break-words text-2xl font-semibold capitalize text-white">{value}</p>
        </div>
    );
}

function CandidateList({ candidates = [] }) {
    if (!candidates.length) {
        return (
            <p className="rounded-lg border border-gray-800 bg-gray-950/40 p-4 text-sm text-gray-500">
                No movable active candidates found.
            </p>
        );
    }

    return (
        <div className="space-y-3">
            {candidates.map((candidate, index) => (
                <div
                    key={candidate.unit_path || `${candidate.unit_name}-${index}`}
                    className="rounded-lg border border-gray-800 bg-gray-950/40 p-4"
                >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                            <p className="break-words font-medium text-white">{candidate.unit_name || 'Unnamed unit'}</p>
                            <p className="mt-1 break-all font-mono text-xs text-gray-500">{candidate.unit_path}</p>
                        </div>
                        <span className="w-fit rounded-md bg-blue-500/10 px-2 py-1 text-xs uppercase text-blue-200">
                            {candidate.unit_kind || 'unit'}
                        </span>
                    </div>

                    {(candidate.evidence || []).length > 0 && (
                        <div className="mt-3 space-y-2">
                            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Evidence</p>
                            {(candidate.evidence || []).slice(0, 4).map((item, evidenceIndex) => (
                                <div
                                    key={`${candidate.unit_path || candidate.unit_name}-${evidenceIndex}`}
                                    className="rounded bg-black/30 px-3 py-2 text-xs text-gray-400"
                                >
                                    <p className="break-words text-gray-300">
                                        {item.source || 'doctor'}: {item.reason || 'active finding'}
                                    </p>
                                    {item.path && <p className="mt-1 break-all font-mono text-gray-500">{item.path}</p>}
                                </div>
                            ))}
                            {candidate.evidence.length > 4 && (
                                <p className="text-xs text-gray-500">
                                    +{candidate.evidence.length - 4} more evidence item(s)
                                </p>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

function PathList({ title, paths = [] }) {
    if (!paths.length) return null;

    return (
        <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">{title}</p>
            <div className="space-y-2">
                {paths.map((path) => (
                    <div key={path} className="rounded-lg border border-gray-800 bg-black/20 px-3 py-2">
                        <p className="break-words text-sm text-white">{unitName(path)}</p>
                        <p className="mt-1 break-all font-mono text-xs text-gray-500">{path}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

function Treatment() {
    const location = useLocation();
    const [simsPath, setSimsPath] = useState(location.state?.simsPath || DEFAULT_SIMS_PATH);
    const [modsPath, setModsPath] = useState(location.state?.modsPath || '');
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showModsPicker, setShowModsPicker] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [progress, setProgress] = useState(null);
    const [busyAction, setBusyAction] = useState(null);
    const [handoff, setHandoff] = useState(null);
    const [handoffCopied, setHandoffCopied] = useState(false);

    const manifestPath = result?.manifest_path || null;
    const candidates = result?.active_candidates || [];
    const nextBatch = result?.next_batch || [];
    const removed = result?.current_removed || [];
    const warnings = result?.warnings || [];
    const blockers = result?.blockers || [];
    const candidateCount = candidates.length;
    const isBusy = Boolean(busyAction);
    const hasBlockers = blockers.length > 0;
    const canPlan = !manifestPath;
    const canStart = result && !manifestPath && candidateCount > 0 && !hasBlockers;
    const canApply = manifestPath && result?.status === 'planned' && nextBatch.length > 0 && !hasBlockers;
    const canRecord = manifestPath && result?.status === 'awaiting_result';
    const canRestore = manifestPath && removed.length > 0;
    const canHandoff = canRequestTreatmentHandoff(result);

    const operationLabel = useMemo(() => {
        if (!busyAction) return null;
        return {
            dryRun: 'Creating dry-run plan',
            start: 'Starting saved session',
            apply: 'Applying next step',
            outcome: 'Recording outcome',
            restore: 'Restoring latest step',
            status: 'Refreshing session status',
            handoff: 'Preparing handoff',
        }[busyAction];
    }, [busyAction]);

    const run = (actionName, action) => {
        setBusyAction(actionName);
        setError(null);
        setProgress(null);
        action({
            onProgress: (nextProgress) => setProgress(nextProgress),
            onComplete: (data) => {
                setResult(data);
                setHandoff(null);
                setHandoffCopied(false);
                setBusyAction(null);
                setProgress(null);
            },
            onError: (message) => {
                if (!manifestPath || !MUTATING_ACTIONS.has(actionName)) {
                    setError(message);
                    setBusyAction(null);
                    setProgress(null);
                    return;
                }

                setError(message);
                setProgress(null);
                setBusyAction('status');
                api.treatmentStatus(manifestPath, {
                    onComplete: (data) => {
                        setResult(data);
                        setHandoff(null);
                        setHandoffCopied(false);
                        setError(message);
                        setBusyAction(null);
                        setProgress(null);
                    },
                    onError: (statusMessage) => {
                        setError(`${message} Could not refresh session status: ${statusMessage}`);
                        setBusyAction(null);
                        setProgress(null);
                    },
                });
            },
        });
    };

    const createPlan = (save = false) => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            return;
        }
        if (!save && !canPlan) {
            setError('Restore or finish the active saved Treatment session before creating a new dry-run plan.');
            return;
        }

        run(save ? 'start' : 'dryRun', (callbacks) =>
            api.planTreatment(simsPath.trim(), modsPath.trim() || null, save, callbacks),
        );
    };

    const startSession = () => {
        if (!window.confirm('Create a saved Treatment session manifest for this plan?')) return;
        createPlan(true);
    };

    const applyStep = () => {
        if (!manifestPath) return;
        if (!window.confirm(`Move ${nextBatch.length} candidate unit(s) out of Mods for the next test?`)) return;
        run('apply', (callbacks) => api.applyTreatment(manifestPath, callbacks));
    };

    const recordOutcome = (outcome) => {
        if (!manifestPath) return;
        if (!window.confirm(OUTCOME_CONFIRMATIONS[outcome] || 'Record this Treatment result?')) return;
        run('outcome', (callbacks) => api.recordTreatmentOutcome(manifestPath, outcome, callbacks));
    };

    const restoreLatest = () => {
        if (!manifestPath) return;
        if (!window.confirm('Restore the latest moved batch back into Mods?')) return;
        run('restore', (callbacks) => api.restoreTreatment(manifestPath, 'latest', callbacks));
    };

    const createHandoff = () => {
        if (!manifestPath) {
            setError('Start a saved Treatment session before creating a handoff.');
            return;
        }

        setBusyAction('handoff');
        setError(null);
        setProgress(null);
        setHandoffCopied(false);
        api.treatmentHandoff(manifestPath, {
            onProgress: (nextProgress) => setProgress(nextProgress),
            onComplete: (data) => {
                const summary = summarizeTreatmentHandoff(data);
                setHandoff(summary);
                setBusyAction(null);
                setProgress(null);
                if (!summary.markdown) {
                    setError('Bridge returned no handoff Markdown.');
                }
            },
            onError: (message) => {
                setError(message);
                setBusyAction(null);
                setProgress(null);
            },
        });
    };

    const copyHandoff = async () => {
        if (!handoff?.markdown) return;
        try {
            await navigator.clipboard.writeText(handoff.markdown);
            setHandoffCopied(true);
            window.setTimeout(() => setHandoffCopied(false), 1800);
        } catch {
            setError('Could not copy handoff Markdown.');
        }
    };

    const downloadHandoff = () => {
        if (!handoff?.markdown) return;
        const blob = new Blob([handoff.markdown], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = treatmentHandoffFilename(handoff.manifestPath || manifestPath);
        link.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-7xl space-y-6">
                <motion.header
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col gap-3"
                >
                    <h1 className="flex items-center gap-3 text-3xl font-bold text-white">
                        <span className="rounded-xl bg-emerald-500/15 p-2 text-emerald-300">
                            <Stethoscope size={28} />
                        </span>
                        Treatment
                    </h1>
                    <p className="max-w-3xl text-gray-400">
                        Build a reversible bisect plan, move one suggested batch at a time, then record what happened
                        after testing in The Sims 4.
                    </p>
                </motion.header>

                <section className="glass-card min-w-0 p-5">
                    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                        <div className="min-w-0">
                            <label className="mb-2 block text-sm font-medium text-gray-300">Sims 4 Folder</label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    value={simsPath}
                                    onChange={(event) => setSimsPath(event.target.value)}
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="min-w-0">
                            <label className="mb-2 block text-sm font-medium text-gray-300">Mods Folder</label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    value={modsPath}
                                    onChange={(event) => setModsPath(event.target.value)}
                                    placeholder="Default: Sims 4 folder / Mods"
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
                                />
                                <button
                                    onClick={() => setShowModsPicker(true)}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Mods folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={() => createPlan(false)}
                                disabled={isBusy || !canPlan}
                                className="flex h-[42px] min-w-0 w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60 sm:px-5 sm:text-base lg:w-auto"
                            >
                                {isBusy ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
                                {canPlan ? 'Dry-Run Plan' : 'Saved Session Active'}
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {(operationLabel || progress) && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-blue-500/30 bg-blue-950/20 p-3 text-sm text-blue-100"
                            >
                                {operationLabel || progress?.stage || 'Working'}
                                {progress ? ` · ${progress.current || 0}/${progress.total || 0}` : ''}
                            </motion.div>
                        )}
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                {result ? (
                    <>
                        <section className="grid gap-4 md:grid-cols-4">
                            <StatTile label="Status" value={statusLabel(result.status)} tone="green" />
                            <StatTile label="Candidates" value={candidateCount} tone={candidateCount ? 'blue' : 'gray'} />
                            <StatTile label="Next Batch" value={nextBatch.length} tone={nextBatch.length ? 'amber' : 'gray'} />
                            <StatTile label="Removed Now" value={removed.length} tone={removed.length ? 'amber' : 'gray'} />
                        </section>

                        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                    <CheckCircle size={20} className="text-emerald-300" />
                                    Active Candidates
                                </h2>
                                <CandidateList candidates={candidates} />
                            </div>

                            <div className="space-y-4">
                                {(warnings.length > 0 || blockers.length > 0) && (
                                    <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
                                        <div className="mb-2 flex items-center gap-2 font-medium">
                                            <AlertTriangle size={18} />
                                            Warnings
                                        </div>
                                        {[...warnings, ...blockers].map((warning) => (
                                            <p key={warning} className="break-words">
                                                {warning}
                                            </p>
                                        ))}
                                    </div>
                                )}

                                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                    <h2 className="mb-4 text-lg font-semibold text-white">Workflow</h2>
                                    <div className="space-y-3">
                                        {canStart && (
                                            <button
                                                onClick={startSession}
                                                disabled={isBusy}
                                                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                <Play size={17} />
                                                Start Saved Session
                                            </button>
                                        )}
                                        {canApply && (
                                            <button
                                                onClick={applyStep}
                                                disabled={isBusy}
                                                className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                <Play size={17} />
                                                Apply Next Step
                                            </button>
                                        )}
                                        {canRecord && (
                                            <div className="space-y-2">
                                                <p className="text-sm text-gray-400">
                                                    Test in The Sims 4, then record what changed.
                                                </p>
                                                {OUTCOME_OPTIONS.map((option) => (
                                                    <button
                                                        key={option.value}
                                                        onClick={() => recordOutcome(option.value)}
                                                        disabled={isBusy}
                                                        className="w-full rounded-lg bg-gray-800 px-4 py-2 text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                                    >
                                                        {option.label}
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                        {canRestore && (
                                            <button
                                                onClick={restoreLatest}
                                                disabled={isBusy}
                                                className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-700 px-4 py-2 font-medium text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                <RotateCcw size={17} />
                                                Restore Latest
                                            </button>
                                        )}
                                        {canHandoff && (
                                            <button
                                                onClick={createHandoff}
                                                disabled={isBusy}
                                                className="flex w-full items-center justify-center gap-2 rounded-lg border border-blue-500/40 px-4 py-2 font-medium text-blue-100 hover:bg-blue-950/40 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                <FileText size={17} />
                                                Prepare Handoff
                                            </button>
                                        )}
                                        {!canStart && !canApply && !canRecord && !canRestore && (
                                            <p className="rounded-lg border border-gray-800 bg-black/20 p-3 text-sm text-gray-500">
                                                No file-moving action is available for the current status.
                                            </p>
                                        )}
                                    </div>

                                    {manifestPath && (
                                        <div className="mt-5">
                                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                                                Manifest
                                            </p>
                                            <p className="break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-400">
                                                {manifestPath}
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {handoff && (
                                    <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                                            <div className="min-w-0">
                                                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                                                    <FileText size={20} className="text-blue-300" />
                                                    {handoff.title}
                                                </h2>
                                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                                                    <span>{handoff.lineCount} lines</span>
                                                    {handoff.status && <span>Status: {statusLabel(handoff.status)}</span>}
                                                    {handoff.sessionId && <span>Session: {handoff.sessionId}</span>}
                                                </div>
                                            </div>
                                            <div className="flex shrink-0 gap-2">
                                                <button
                                                    onClick={copyHandoff}
                                                    disabled={!handoff.markdown}
                                                    className="flex h-10 w-10 items-center justify-center rounded-lg border border-gray-700 text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                                                    title="Copy handoff Markdown"
                                                >
                                                    <Copy size={17} />
                                                </button>
                                                <button
                                                    onClick={downloadHandoff}
                                                    disabled={!handoff.markdown}
                                                    className="flex h-10 w-10 items-center justify-center rounded-lg border border-gray-700 text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                                                    title="Download handoff Markdown"
                                                >
                                                    <Download size={17} />
                                                </button>
                                            </div>
                                        </div>
                                        {handoffCopied && (
                                            <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-3 py-2 text-sm text-emerald-200">
                                                Copied Markdown
                                            </p>
                                        )}
                                        {handoff.manifestPath && (
                                            <p className="mt-4 break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-500">
                                                {handoff.manifestPath}
                                            </p>
                                        )}
                                        <textarea
                                            readOnly
                                            value={handoff.markdown}
                                            className="mt-4 h-72 w-full resize-y rounded-lg border border-gray-800 bg-black/30 p-3 font-mono text-xs leading-relaxed text-gray-200 outline-none"
                                            spellCheck="false"
                                        />
                                    </div>
                                )}

                                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                    <div className="space-y-4">
                                        <PathList title="Next Batch" paths={nextBatch} />
                                        <PathList title="Currently Removed" paths={removed} />
                                    </div>
                                </div>
                            </div>
                        </section>
                    </>
                ) : (
                    <section className="flex min-h-[280px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-gray-900/40 text-center">
                        <Stethoscope className="mb-4 text-gray-600" size={52} />
                        <h2 className="text-xl font-semibold text-white">No Treatment plan yet</h2>
                        <p className="mt-2 max-w-md text-sm text-gray-500">
                            Start with a dry-run plan. It reads the current Doctor evidence without moving files.
                        </p>
                    </section>
                )}

                <FilePicker
                    isOpen={showSimsPicker}
                    onClose={() => setShowSimsPicker(false)}
                    onSelect={(path) => setSimsPath(path)}
                    initialPath={simsPath}
                    selectDirectory={true}
                />
                <FilePicker
                    isOpen={showModsPicker}
                    onClose={() => setShowModsPicker(false)}
                    onSelect={(path) => setModsPath(path)}
                    initialPath={modsPath || simsPath}
                    selectDirectory={true}
                />
            </div>
        </div>
    );
}

export default Treatment;
