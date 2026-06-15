import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    Archive,
    CheckSquare,
    ClipboardList,
    Files,
    FileJson,
    FileWarning,
    FolderOpen,
    Loader2,
    Play,
    RefreshCw,
    RotateCcw,
    ShieldCheck,
    Square,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import {
    canApplyCleanupOperation,
    canRestoreCleanupOperation,
    canStageCleanupOperation,
    flattenCleanupActions,
    selectAllCleanupActions,
    summarizeCleanupOperation,
    summarizeCleanupPlan,
    toggleCleanupAction,
} from './cleanupModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';
const DEFAULT_PLAN_PATH = '~/Documents/simanalysis-cleanup-plan.json';

function StatTile({ label, value, tone = 'blue' }) {
    const tones = {
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-200',
        green: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200',
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-2 break-words text-2xl font-semibold text-white">{value}</p>
        </div>
    );
}

function CategoryMetric({ label, value }) {
    return (
        <div className="flex items-center justify-between gap-3 border-b border-gray-800 py-3 last:border-b-0">
            <span className="text-sm text-gray-400">{label}</span>
            <span className="rounded-md bg-gray-800 px-2 py-1 font-mono text-sm text-white">{value}</span>
        </div>
    );
}

function PathField({ label, value, onChange, onBrowse, placeholder, browseTitle }) {
    return (
        <div className="min-w-0">
            <label className="mb-2 block text-sm font-medium text-gray-300">{label}</label>
            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                <input
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    placeholder={placeholder}
                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
                />
                <button
                    onClick={onBrowse}
                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700"
                    title={browseTitle}
                >
                    <FolderOpen size={18} />
                </button>
            </div>
        </div>
    );
}

function ActionCard({ action, disabled = false, selected = false, onToggle }) {
    return (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex min-w-0 gap-3">
                    <input
                        type="checkbox"
                        checked={selected}
                        disabled={disabled}
                        onChange={(event) => onToggle?.(action.id, event.target.checked)}
                        aria-label={`Select cleanup action ${action.id}`}
                        className="mt-1 h-5 w-5 shrink-0 rounded border-gray-600 bg-gray-900 text-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                    />
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-xs uppercase text-blue-200">
                                {action.categoryLabel}
                            </span>
                            <span className="rounded-md border border-gray-700 px-2 py-1 text-xs uppercase text-gray-300">
                                {action.severity}
                            </span>
                        </div>
                        <p className="mt-3 break-words font-medium text-white">{action.title}</p>
                        <p className="mt-1 break-words text-sm text-gray-400">{action.reason}</p>
                    </div>
                </div>
                <p className="w-fit rounded-md bg-gray-800 px-2 py-1 font-mono text-xs text-gray-300">
                    {action.id}
                </p>
            </div>
            <div className="mt-4 grid gap-3 xl:grid-cols-2">
                <div className="min-w-0">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Source</p>
                    <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-300">
                        {action.source || '(unknown)'}
                    </p>
                </div>
                <div className="min-w-0">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Destination</p>
                    <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-300">
                        {action.destination || '(not proposed)'}
                    </p>
                </div>
            </div>
            {action.keepCandidate && (
                <p className="mt-3 break-all rounded border border-emerald-500/20 bg-emerald-950/10 px-3 py-2 font-mono text-xs text-emerald-200">
                    Keep: {action.keepCandidate}
                </p>
            )}
        </div>
    );
}

function ActionSelectionBar({ selectedCount, actionCount, onSelectAll, onClear }) {
    return (
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-gray-400">
                {selectedCount}/{actionCount} selected
            </p>
            <div className="flex gap-2">
                <button
                    onClick={onSelectAll}
                    className="flex h-9 items-center gap-2 rounded-lg border border-gray-700 px-3 text-sm text-gray-200 hover:bg-gray-800"
                >
                    <CheckSquare size={16} />
                    Select All
                </button>
                <button
                    onClick={onClear}
                    className="flex h-9 items-center gap-2 rounded-lg border border-gray-700 px-3 text-sm text-gray-200 hover:bg-gray-800"
                >
                    <Square size={16} />
                    Clear
                </button>
            </div>
        </div>
    );
}

function OperationStatus({ summary, onRefresh, onApply, onRestore, canApply, canRestore, busy }) {
    if (!summary.manifestPath) {
        return null;
    }

    const statusRows = Object.entries(summary.statusCounts);

    return (
        <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                    <FileJson size={20} className="text-blue-300" />
                    Operation
                </h2>
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={onRefresh}
                        disabled={busy}
                        className="flex h-9 items-center gap-2 rounded-lg border border-gray-700 px-3 text-sm text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {busy ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        Status
                    </button>
                    <button
                        onClick={onApply}
                        disabled={!canApply || busy}
                        className="flex h-9 items-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <Play size={16} />
                        Apply
                    </button>
                    <button
                        onClick={onRestore}
                        disabled={!canRestore || busy}
                        className="flex h-9 items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-950/20 px-3 text-sm font-medium text-amber-100 hover:bg-amber-900/30 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <RotateCcw size={16} />
                        Restore
                    </button>
                </div>
            </div>

            <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Status</p>
                        <p className="rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                            {summary.status || 'unknown'}
                        </p>
                    </div>
                    <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</p>
                        <p className="rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                            {summary.actionCount}
                        </p>
                    </div>
                </div>
                <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Manifest</p>
                    <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-300">
                        {summary.manifestPath}
                    </p>
                </div>
                {statusRows.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {statusRows.map(([status, value]) => (
                            <span key={status} className="rounded-md border border-gray-700 bg-gray-950 px-2 py-1 font-mono text-xs text-gray-300">
                                {status}: {value}
                            </span>
                        ))}
                    </div>
                )}
                {[...summary.blockers, ...summary.errors].map((message) => (
                    <p key={message} className="break-words rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-200">
                        {message}
                    </p>
                ))}
                {summary.warnings.map((warning) => (
                    <p key={warning} className="break-words rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-sm text-amber-100">
                        {warning}
                    </p>
                ))}
            </div>
        </div>
    );
}

function ConfirmOperationModal({ kind, summary, busy, onCancel, onConfirm }) {
    if (!kind) {
        return null;
    }

    const isRestore = kind === 'restore';
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-lg rounded-xl border border-gray-700 bg-gray-950 p-5 shadow-2xl">
                <h2 className="text-xl font-semibold text-white">
                    {isRestore ? 'Restore cleanup operation' : 'Apply cleanup operation'}
                </h2>
                <div className="mt-4 space-y-3 text-sm text-gray-300">
                    <p className="break-all rounded-lg border border-gray-800 bg-black/30 p-3 font-mono text-xs">
                        {summary.manifestPath}
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
                            <p className="text-xs uppercase tracking-wider text-gray-500">Status</p>
                            <p className="mt-1 font-mono text-white">{summary.status || 'unknown'}</p>
                        </div>
                        <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
                            <p className="text-xs uppercase tracking-wider text-gray-500">Actions</p>
                            <p className="mt-1 font-mono text-white">{summary.actionCount}</p>
                        </div>
                    </div>
                    <p className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-amber-100">
                        {isRestore
                            ? 'Restore moves files back according to this manifest.'
                            : 'Apply moves only the actions already staged in this manifest.'}
                    </p>
                </div>
                <div className="mt-5 flex justify-end gap-2">
                    <button
                        onClick={onCancel}
                        disabled={busy}
                        className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={busy}
                        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 ${
                            isRestore ? 'bg-amber-600 hover:bg-amber-500' : 'bg-emerald-600 hover:bg-emerald-500'
                        }`}
                    >
                        {busy && <Loader2 className="animate-spin" size={16} />}
                        {isRestore ? 'Restore' : 'Apply'}
                    </button>
                </div>
            </div>
        </div>
    );
}

function Cleanup() {
    const [simsPath, setSimsPath] = useProfileDefaultPath('simsPath', {
        fallback: DEFAULT_SIMS_PATH,
    });
    const [dbPath, setDbPath] = useState('');
    const [planPath, setPlanPath] = useState(DEFAULT_PLAN_PATH);
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showDbPicker, setShowDbPicker] = useState(false);
    const [showPlanPicker, setShowPlanPicker] = useState(false);
    const [plan, setPlan] = useState(null);
    const [operation, setOperation] = useState(null);
    const [error, setError] = useState(null);
    const [operationError, setOperationError] = useState(null);
    const [progress, setProgress] = useState(null);
    const [busy, setBusy] = useState(false);
    const [operationBusy, setOperationBusy] = useState(false);
    const [selectedActionIds, setSelectedActionIds] = useState([]);
    const [confirmKind, setConfirmKind] = useState(null);

    const summary = useMemo(() => summarizeCleanupPlan(plan || {}), [plan]);
    const actions = useMemo(() => flattenCleanupActions(plan || {}), [plan]);
    const operationSummary = useMemo(() => summarizeCleanupOperation(operation || {}), [operation]);
    const canStageSelected = canStageCleanupOperation({
        planPath,
        selectedActionIds,
        allActions: false,
        actionCount: actions.length,
    });
    const canStageAll = canStageCleanupOperation({
        planPath,
        selectedActionIds: [],
        allActions: true,
        actionCount: actions.length,
    });
    const canApplyOperation = canApplyCleanupOperation(operation || {});
    const canRestoreOperation = canRestoreCleanupOperation(operation || {});

    const runPlan = () => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            return;
        }

        setBusy(true);
        setError(null);
        setOperationError(null);
        setProgress(null);
        api.cleanupPlan(simsPath.trim(), {
            onProgress: (nextProgress) => setProgress(nextProgress),
            onComplete: (data) => {
                setPlan(data);
                setOperation(null);
                setSelectedActionIds([]);
                setBusy(false);
                setProgress(null);
            },
            onError: (message) => {
                setError(message);
                setBusy(false);
                setProgress(null);
            },
        }, {
            db: dbPath.trim() || undefined,
            exportPath: planPath.trim() || undefined,
        });
    };

    const toggleAction = (actionId, checked) => {
        setSelectedActionIds((current) => toggleCleanupAction(current, actionId, checked));
    };

    const stageOperation = (allActions = false) => {
        if (!canStageCleanupOperation({
            planPath,
            selectedActionIds: allActions ? [] : selectedActionIds,
            allActions,
            actionCount: actions.length,
        })) {
            setOperationError('Choose cleanup actions and keep a cleanup plan JSON path.');
            return;
        }

        setOperationBusy(true);
        setOperationError(null);
        api.cleanupStage(simsPath.trim(), {
            onComplete: (data) => {
                setOperation(data);
                setOperationBusy(false);
            },
            onError: (message) => {
                setOperationError(message);
                setOperationBusy(false);
            },
        }, {
            planPath: planPath.trim(),
            actions: allActions ? [] : selectedActionIds,
            allActions,
        });
    };

    const refreshOperation = () => {
        if (!operationSummary.manifestPath) {
            return;
        }

        setOperationBusy(true);
        setOperationError(null);
        api.cleanupStatus(operationSummary.manifestPath, {
            onComplete: (data) => {
                setOperation(data);
                setOperationBusy(false);
            },
            onError: (message) => {
                setOperationError(message);
                setOperationBusy(false);
            },
        });
    };

    const commitOperation = (kind) => {
        if (!operationSummary.manifestPath) {
            return;
        }

        const runner = kind === 'restore' ? api.cleanupRestore : api.cleanupApply;
        setOperationBusy(true);
        setOperationError(null);
        runner(operationSummary.manifestPath, {
            onComplete: (data) => {
                setOperation(data);
                setOperationBusy(false);
                setConfirmKind(null);
            },
            onError: (message) => {
                setOperationError(message);
                setOperationBusy(false);
                setConfirmKind(null);
            },
        });
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
                        <span className="rounded-xl bg-blue-500/15 p-2 text-blue-300">
                            <ClipboardList size={28} />
                        </span>
                        Cleanup
                    </h1>
                    <div className="flex flex-wrap gap-2 text-xs uppercase tracking-wider">
                        <span className="rounded-md border border-emerald-500/30 bg-emerald-950/20 px-2 py-1 text-emerald-200">
                            Manifest-first ops
                        </span>
                        <span className="rounded-md border border-gray-700 px-2 py-1 text-gray-400">
                            No raw delete
                        </span>
                    </div>
                </motion.header>

                <section className="glass-card min-w-0 p-5">
                    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
                        <PathField
                            label="Sims 4 Folder"
                            value={simsPath}
                            onChange={setSimsPath}
                            onBrowse={() => setShowSimsPicker(true)}
                            browseTitle="Browse for Sims 4 folder"
                        />
                        <PathField
                            label="Inventory DB"
                            value={dbPath}
                            onChange={setDbPath}
                            onBrowse={() => setShowDbPicker(true)}
                            placeholder="Default ledger database"
                            browseTitle="Browse for inventory database"
                        />
                        <PathField
                            label="Plan JSON"
                            value={planPath}
                            onChange={setPlanPath}
                            onBrowse={() => setShowPlanPicker(true)}
                            placeholder="External cleanup plan JSON"
                            browseTitle="Browse for cleanup plan JSON"
                        />
                        <div className="flex items-end">
                            <button
                                onClick={runPlan}
                                disabled={busy}
                                className="flex h-[42px] min-w-0 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60 sm:px-5 sm:text-base lg:w-auto"
                            >
                                {busy ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
                                Review Plan
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {(busy || progress) && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-blue-500/30 bg-blue-950/20 p-3 text-sm text-blue-100"
                            >
                                {progress?.stage || 'Building cleanup review'}
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
                        {operationError && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                {operationError}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                {plan ? (
                    <>
                        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
                            <StatTile label="Files" value={summary.filesConsidered} tone="blue" />
                            <StatTile label="Findings" value={summary.findingCount} tone={summary.findingCount ? 'amber' : 'green'} />
                            <StatTile label="Actions" value={summary.actionCount} tone={summary.actionCount ? 'amber' : 'green'} />
                            <StatTile label="Duplicates" value={summary.duplicateGroups} tone={summary.duplicateGroups ? 'amber' : 'gray'} />
                            <StatTile label="Archives" value={summary.archives} tone={summary.archives ? 'amber' : 'gray'} />
                            <StatTile label="Support" value={summary.supportFiles} tone={summary.supportFiles ? 'amber' : 'gray'} />
                        </section>

                        <section className="grid gap-6 xl:grid-cols-[0.75fr_1.25fr]">
                            <div className="space-y-4">
                                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                    <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                        <Files size={20} className="text-blue-300" />
                                        Plan
                                    </h2>
                                    <div className="space-y-3 text-sm">
                                        {summary.planId && (
                                            <p className="break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-400">
                                                {summary.planId}
                                            </p>
                                        )}
                                        <p className="break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-400">
                                            {summary.rootPath || simsPath}
                                        </p>
                                        {summary.dbPath && (
                                            <p className="break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-500">
                                                {summary.dbPath}
                                            </p>
                                        )}
                                    </div>
                                </div>

                                {summary.warnings.length > 0 && (
                                    <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
                                        <div className="mb-2 flex items-center gap-2 font-medium">
                                            <AlertTriangle size={18} />
                                            Warnings
                                        </div>
                                        <div className="space-y-2">
                                            {summary.warnings.map((warning) => (
                                                <p key={warning} className="break-words">
                                                    {warning}
                                                </p>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                    <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                        <Archive size={20} className="text-amber-300" />
                                        Categories
                                    </h2>
                                    <div>
                                        <CategoryMetric label="Resource.cfg" value={summary.duplicateResourceCfg} />
                                        <CategoryMetric label="Tray Files" value={summary.misplacedTray} />
                                    </div>
                                </div>

                                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                    <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                        <ShieldCheck size={20} className="text-emerald-300" />
                                        Operating Table
                                    </h2>
                                    <div className="space-y-3">
                                        <p className="break-all rounded-lg border border-gray-800 bg-black/20 p-3 font-mono text-xs text-gray-400">
                                            {planPath || '(no plan path)'}
                                        </p>
                                        <div className="grid gap-2 sm:grid-cols-2">
                                            <button
                                                onClick={() => stageOperation(false)}
                                                disabled={!canStageSelected || operationBusy}
                                                className="flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                {operationBusy ? <Loader2 className="animate-spin" size={16} /> : <FileJson size={16} />}
                                                Stage Selected
                                            </button>
                                            <button
                                                onClick={() => stageOperation(true)}
                                                disabled={!canStageAll || operationBusy}
                                                className="flex h-10 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-950/20 px-3 text-sm font-medium text-blue-100 hover:bg-blue-900/30 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                <CheckSquare size={16} />
                                                Stage All
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <OperationStatus
                                    summary={operationSummary}
                                    onRefresh={refreshOperation}
                                    onApply={() => setConfirmKind('apply')}
                                    onRestore={() => setConfirmKind('restore')}
                                    canApply={canApplyOperation}
                                    canRestore={canRestoreOperation}
                                    busy={operationBusy}
                                />
                            </div>

                            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                    <FileWarning size={20} className="text-amber-300" />
                                    Review Actions
                                </h2>
                                {actions.length ? (
                                    <div className="space-y-3">
                                        <ActionSelectionBar
                                            selectedCount={selectedActionIds.length}
                                            actionCount={actions.length}
                                            onSelectAll={() => setSelectedActionIds(selectAllCleanupActions(actions))}
                                            onClear={() => setSelectedActionIds([])}
                                        />
                                        {actions.map((action) => (
                                            <ActionCard
                                                key={action.id || `${action.source}-${action.destination}`}
                                                action={action}
                                                disabled={operationBusy}
                                                selected={selectedActionIds.includes(action.id)}
                                                onToggle={toggleAction}
                                            />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-black/20 text-center">
                                        <ShieldCheck className="mb-4 text-emerald-500/50" size={52} />
                                        <h3 className="text-xl font-semibold text-white">No review actions</h3>
                                        <p className="mt-2 max-w-md text-sm text-gray-500">
                                            The latest ledger snapshot produced no cleanup findings.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </section>
                    </>
                ) : (
                    <section className="flex min-h-[280px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-gray-900/40 text-center">
                        <ClipboardList className="mb-4 text-gray-600" size={52} />
                        <h2 className="text-xl font-semibold text-white">No cleanup plan yet</h2>
                        <p className="mt-2 max-w-md text-sm text-gray-500">
                            Review findings come from the latest inventory ledger snapshot.
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
                    isOpen={showDbPicker}
                    onClose={() => setShowDbPicker(false)}
                    onSelect={(path) => setDbPath(path)}
                    initialPath={dbPath || simsPath}
                    selectDirectory={false}
                />
                <FilePicker
                    isOpen={showPlanPicker}
                    onClose={() => setShowPlanPicker(false)}
                    onSelect={(path) => setPlanPath(path)}
                    initialPath={planPath}
                    selectDirectory={false}
                />
                <ConfirmOperationModal
                    kind={confirmKind}
                    summary={operationSummary}
                    busy={operationBusy}
                    onCancel={() => setConfirmKind(null)}
                    onConfirm={() => commitOperation(confirmKind)}
                />
            </div>
        </div>
    );
}

export default Cleanup;
