import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    CheckSquare,
    FileJson,
    FolderOpen,
    HardDrive,
    Loader2,
    RefreshCw,
    RotateCcw,
    ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import {
    canApplyCachePlan,
    getEligibleCacheActionRows,
    selectAllCacheActions,
    summarizeCacheCleanupPlan,
    summarizeCacheOperation,
    summarizeCacheStatus,
    toCachePlanActionRows,
    toCacheTargetRows,
    toggleCacheActionSelection,
} from './cacheDoctorModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';
const DEFAULT_PLAN_PATH = '~/Documents/simanalysis-cache-plan.json';
const PLAN_STORAGE_KEY = 'cache-doctor-plan-path';

const toneClasses = {
    blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
    amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
    green: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
    red: 'border-red-500/30 bg-red-950/20 text-red-100',
};

function PathField({ value, onChange, onBrowse }) {
    return (
        <div className="min-w-0">
            <label className="mb-2 block text-sm font-medium text-gray-300">Sims 4 Folder</label>
            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                <input
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    placeholder={DEFAULT_SIMS_PATH}
                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
                />
                <button
                    onClick={onBrowse}
                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700"
                    title="Choose Sims 4 folder"
                >
                    <FolderOpen size={18} />
                </button>
            </div>
        </div>
    );
}

function PlanPathField({ value, onChange }) {
    return (
        <div className="min-w-0">
            <label className="mb-2 block text-sm font-medium text-gray-300">Plan JSON</label>
            <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder={DEFAULT_PLAN_PATH}
                className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
            />
        </div>
    );
}

function StatTile({ icon: Icon, label, value, tone = 'blue' }) {
    return (
        <div className={`rounded-xl border p-4 ${toneClasses[tone] || toneClasses.blue}`}>
            <div className="flex items-center gap-3">
                <Icon size={20} />
                <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
                    <p className="mt-1 break-words text-2xl font-semibold text-white">{value}</p>
                </div>
            </div>
        </div>
    );
}

function Badge({ tone = 'blue', children }) {
    const className = tone === 'green'
        ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100'
        : tone === 'amber'
            ? 'border-amber-500/30 bg-amber-950/20 text-amber-100'
            : tone === 'red'
                ? 'border-red-500/30 bg-red-950/20 text-red-100'
                : 'border-blue-500/30 bg-blue-950/20 text-blue-100';

    return (
        <span className={`inline-flex w-fit rounded-md border px-2 py-1 text-xs uppercase ${className}`}>
            {children}
        </span>
    );
}

function actionTone(row) {
    if (row.status === 'blocked') return 'red';
    if (row.status === 'planned') return 'green';
    return 'blue';
}

function MessageList({ icon: Icon, title, messages, tone }) {
    if (!messages?.length) return null;
    const toneClass = tone === 'red'
        ? 'border-red-500/25 bg-red-950/10 text-red-100'
        : 'border-blue-500/25 bg-blue-950/10 text-blue-100';

    return (
        <section className={`rounded-xl border p-5 ${toneClass}`}>
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-white">
                <Icon size={18} />
                {title}
            </h2>
            <div className="space-y-2">
                {messages.map((message) => (
                    <p key={message} className="break-words text-sm opacity-85">{message}</p>
                ))}
            </div>
        </section>
    );
}

function TargetTable({ rows }) {
    if (rows.length === 0) {
        return (
            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5 text-sm text-gray-500">
                No cache status loaded.
            </div>
        );
    }

    return (
        <>
            <div className="space-y-3 md:hidden">
                {rows.map((row) => (
                    <div key={row.id} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
                        <div className="flex flex-col gap-2">
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="font-medium text-white">{row.label}</p>
                                    <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                        {row.relativePath}
                                    </p>
                                </div>
                                <span className={`shrink-0 rounded-md border px-2 py-1 text-xs uppercase ${
                                    row.present
                                        ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100'
                                        : 'border-gray-700 bg-black/20 text-gray-300'
                                }`}>
                                    {row.statusLabel}
                                </span>
                            </div>
                            {row.reason && <p className="text-sm text-gray-400">{row.reason}</p>}
                            <div className="grid grid-cols-3 gap-2 text-xs text-gray-400">
                                <div>
                                    <p className="uppercase tracking-wider text-gray-600">Risk</p>
                                    <p className="mt-1 text-gray-200">{row.riskLabel}</p>
                                </div>
                                <div>
                                    <p className="uppercase tracking-wider text-gray-600">Size</p>
                                    <p className="mt-1 font-mono text-gray-200">{row.sizeLabel}</p>
                                </div>
                                <div>
                                    <p className="uppercase tracking-wider text-gray-600">Items</p>
                                    <p className="mt-1 font-mono text-gray-200">{row.itemCount}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            <div className="hidden overflow-x-auto rounded-xl border border-gray-800 md:block">
                <table className="min-w-full divide-y divide-gray-800 text-sm">
                    <thead className="bg-gray-950/60 text-left text-xs uppercase tracking-wider text-gray-500">
                        <tr>
                            <th className="px-4 py-3 font-medium">Target</th>
                            <th className="px-4 py-3 font-medium">Status</th>
                            <th className="px-4 py-3 font-medium">Risk</th>
                            <th className="px-4 py-3 font-medium">Size</th>
                            <th className="px-4 py-3 font-medium">Items</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800 bg-gray-900/30">
                    {rows.map((row) => (
                        <tr key={row.id} className="align-top">
                            <td className="px-4 py-3">
                                <p className="font-medium text-white">{row.label}</p>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">{row.relativePath}</p>
                                {row.reason && <p className="mt-2 text-xs text-gray-400">{row.reason}</p>}
                            </td>
                            <td className="px-4 py-3">
                                <span className={`inline-flex rounded-md border px-2 py-1 text-xs uppercase ${
                                    row.present
                                        ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100'
                                        : 'border-gray-700 bg-black/20 text-gray-300'
                                }`}>
                                    {row.statusLabel}
                                </span>
                                <p className="mt-2 text-xs text-gray-500">{row.kindLabel}</p>
                            </td>
                            <td className="px-4 py-3 text-gray-300">{row.riskLabel}</td>
                            <td className="px-4 py-3 font-mono text-gray-200">{row.sizeLabel}</td>
                            <td className="px-4 py-3 font-mono text-gray-200">{row.itemCount}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}

function PlanActions({ rows, selectedActionIds, onToggleAction }) {
    if (rows.length === 0) {
        return (
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-5 text-sm text-gray-500">
                No cache cleanup plan loaded.
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {rows.map((row) => {
                const eligible = row.status === 'planned' && row.type === 'quarantine_cache_target';
                return (
                    <div key={row.id} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
                        <div className="grid gap-3 sm:grid-cols-[24px_minmax(0,1fr)_auto] sm:items-start">
                            <input
                                type="checkbox"
                                checked={selectedActionIds.includes(row.id)}
                                onChange={(event) => onToggleAction(row.id, event.target.checked)}
                                disabled={!eligible}
                                className="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-900 text-emerald-500 disabled:opacity-40"
                                aria-label={`Select cache action ${row.id}`}
                            />
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                    <p className="break-words font-medium text-white">{row.label}</p>
                                    <Badge tone={actionTone(row)}>{row.statusLabel}</Badge>
                                </div>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                    {row.sourceRelativePath}
                                </p>
                                <p className="mt-2 break-all font-mono text-xs text-gray-500">
                                    {row.quarantineRelativePath}
                                </p>
                                {row.blockers.length > 0 && (
                                    <div className="mt-3 space-y-1">
                                        {row.blockers.map((blocker) => (
                                            <p key={blocker} className="break-words text-xs text-red-200">
                                                {blocker}
                                            </p>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs text-gray-400 sm:w-44">
                                <div>
                                    <p className="uppercase tracking-wider text-gray-600">Size</p>
                                    <p className="mt-1 font-mono text-gray-200">{row.expectedSizeLabel}</p>
                                </div>
                                <div>
                                    <p className="uppercase tracking-wider text-gray-600">Items</p>
                                    <p className="mt-1 font-mono text-gray-200">{row.expectedItemCount}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function OperationPanel({ summary, onRefresh, onRestore, busy }) {
    if (!summary.manifestPath) {
        return (
            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
                    <RotateCcw size={18} />
                    Operation
                </h2>
                <p className="text-sm text-gray-500">No cache operation manifest loaded.</p>
            </section>
        );
    }

    return (
        <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                    <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                        <RotateCcw size={18} />
                        Operation
                    </h2>
                    <p className="mt-2 break-all font-mono text-xs text-gray-500">{summary.manifestPath}</p>
                </div>
                <Badge tone={summary.tone}>{summary.statusLabel}</Badge>
            </div>
            <div className="mb-4 grid gap-2 text-sm sm:grid-cols-3">
                <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                    <p className="text-xs uppercase tracking-wider text-gray-600">Quarantined</p>
                    <p className="mt-1 font-mono text-lg text-white">{summary.quarantinedCount}</p>
                </div>
                <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                    <p className="text-xs uppercase tracking-wider text-gray-600">Restored</p>
                    <p className="mt-1 font-mono text-lg text-white">{summary.restoredCount}</p>
                </div>
                <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                    <p className="text-xs uppercase tracking-wider text-gray-600">Blocked</p>
                    <p className="mt-1 font-mono text-lg text-white">{summary.blockedCount}</p>
                </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
                <button
                    onClick={onRefresh}
                    disabled={busy}
                    className="flex h-[42px] items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 text-sm font-medium text-gray-100 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {busy ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                    Refresh
                </button>
                <button
                    onClick={onRestore}
                    disabled={busy || !summary.canRestore}
                    className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {busy ? <Loader2 className="animate-spin" size={16} /> : <RotateCcw size={16} />}
                    Restore
                </button>
            </div>
        </section>
    );
}

function readStoredPlanPath() {
    if (typeof localStorage === 'undefined') return DEFAULT_PLAN_PATH;
    return localStorage.getItem(PLAN_STORAGE_KEY) || DEFAULT_PLAN_PATH;
}

function CacheDoctor() {
    const [simsPath, setSimsPath] = useProfileDefaultPath('cachePath', {
        storageKey: 'cache-doctor-root-path',
        fallback: DEFAULT_SIMS_PATH,
    });
    const [showFilePicker, setShowFilePicker] = useState(false);
    const [status, setStatus] = useState(null);
    const [planPath, setPlanPath] = useState(readStoredPlanPath);
    const [plan, setPlan] = useState(null);
    const [selectedActionIds, setSelectedActionIds] = useState([]);
    const [confirmApply, setConfirmApply] = useState(false);
    const [operation, setOperation] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isPlanning, setIsPlanning] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const [isRestoring, setIsRestoring] = useState(false);
    const [error, setError] = useState(null);

    const summary = useMemo(() => summarizeCacheStatus(status || {}), [status]);
    const rows = useMemo(() => toCacheTargetRows(status || {}), [status]);
    const planSummary = useMemo(() => summarizeCacheCleanupPlan(plan || {}), [plan]);
    const planRows = useMemo(() => toCachePlanActionRows(plan || {}), [plan]);
    const eligibleRows = useMemo(() => getEligibleCacheActionRows(planRows), [planRows]);
    const operationSummary = useMemo(() => summarizeCacheOperation(operation || {}), [operation]);
    const canApply = canApplyCachePlan({
        planPath,
        selectedActionIds,
        eligibleActionCount: eligibleRows.length,
    }) && confirmApply;

    const handleStatus = () => {
        const target = simsPath.trim();
        if (!target) {
            toast.error('Choose a Sims 4 folder first');
            return;
        }

        localStorage.setItem('cache-doctor-root-path', target);
        setError(null);
        setIsLoading(true);
        api.cacheStatus(target, {
            onComplete: (result) => {
                setStatus(result);
                setIsLoading(false);
                toast.success('Cache Doctor status updated');
            },
            onError: (message) => {
                setError(message);
                setIsLoading(false);
                toast.error(`Cache Doctor status failed: ${message}`);
            },
        });
    };

    const handlePlan = () => {
        const target = simsPath.trim();
        const output = planPath.trim();
        if (!target || !output) {
            toast.error('Choose a Sims 4 folder and cache plan path first');
            return;
        }

        localStorage.setItem('cache-doctor-root-path', target);
        localStorage.setItem(PLAN_STORAGE_KEY, output);
        setError(null);
        setIsPlanning(true);
        api.cachePlan(target, {
            onComplete: (result) => {
                const actionRows = toCachePlanActionRows(result);
                setPlan(result);
                setSelectedActionIds(selectAllCacheActions(actionRows));
                setConfirmApply(false);
                setIsPlanning(false);
                toast.success('Cache cleanup plan written');
            },
            onError: (message) => {
                setError(message);
                setIsPlanning(false);
                toast.error(`Cache cleanup plan failed: ${message}`);
            },
        }, { exportPath: output });
    };

    const handleToggleAction = (actionId, checked) => {
        setSelectedActionIds((current) => toggleCacheActionSelection(current, actionId, checked));
        setConfirmApply(false);
    };

    const handleApply = () => {
        if (!canApply) {
            toast.error('Choose cache actions and confirm quarantine before applying');
            return;
        }

        setError(null);
        setIsApplying(true);
        api.cacheApply(planPath.trim(), {
            onComplete: (result) => {
                setOperation(result);
                setConfirmApply(false);
                setIsApplying(false);
                toast.success('Cache targets quarantined');
                handleStatus();
            },
            onError: (message) => {
                setError(message);
                setIsApplying(false);
                toast.error(`Cache quarantine failed: ${message}`);
            },
        }, { actions: selectedActionIds });
    };

    const handleOperationStatus = () => {
        const manifestPath = operationSummary.manifestPath;
        if (!manifestPath) return;
        setError(null);
        setIsRestoring(true);
        api.cacheOperationStatus(manifestPath, {
            onComplete: (result) => {
                setOperation(result);
                setIsRestoring(false);
                toast.success('Cache operation refreshed');
            },
            onError: (message) => {
                setError(message);
                setIsRestoring(false);
                toast.error(`Cache operation refresh failed: ${message}`);
            },
        });
    };

    const handleRestore = () => {
        const manifestPath = operationSummary.manifestPath;
        if (!manifestPath || !operationSummary.canRestore) {
            toast.error('No restorable cache operation is loaded');
            return;
        }
        setError(null);
        setIsRestoring(true);
        api.cacheRestore(manifestPath, {
            onComplete: (result) => {
                setOperation(result);
                setIsRestoring(false);
                toast.success('Cache targets restored');
                handleStatus();
            },
            onError: (message) => {
                setError(message);
                setIsRestoring(false);
                toast.error(`Cache restore failed: ${message}`);
            },
        });
    };

    return (
        <div className="min-w-0 space-y-6 p-4 md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3">
                        <div className="rounded-xl bg-cyan-500/15 p-3 text-cyan-200">
                            <HardDrive size={26} />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-white">Cache Doctor</h1>
                            <p className="text-gray-400">Cache status and review boundary</p>
                        </div>
                    </div>
                </div>
            </div>

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                    <PathField
                        value={simsPath}
                        onChange={setSimsPath}
                        onBrowse={() => setShowFilePicker(true)}
                    />
                    <button
                        onClick={handleStatus}
                        disabled={isLoading}
                        className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isLoading ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        Status
                    </button>
                </div>
            </section>

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px] xl:items-end">
                    <PlanPathField value={planPath} onChange={setPlanPath} />
                    <button
                        onClick={handlePlan}
                        disabled={isPlanning}
                        className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 text-sm font-medium text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isPlanning ? <Loader2 className="animate-spin" size={16} /> : <FileJson size={16} />}
                        Plan
                    </button>
                </div>
            </section>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-200">
                    {error}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatTile icon={ShieldCheck} label="Boundary" value={summary.readOnlyLabel} tone={summary.readOnlyLabel === 'Read-only' ? 'green' : 'red'} />
                <StatTile icon={HardDrive} label="Targets" value={summary.presentCount} tone={summary.tone} />
                <StatTile icon={CheckCircle2} label="Size" value={summary.totalSizeLabel} tone="blue" />
                <StatTile icon={AlertTriangle} label="Warnings" value={summary.warningCount} tone={summary.warningCount ? 'red' : 'green'} />
            </div>

            <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                            <h2 className="text-lg font-semibold text-white">Cleanup Plan</h2>
                            <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                {planSummary.manifestPath || planPath}
                            </p>
                        </div>
                        <Badge tone={planSummary.tone}>{planSummary.statusLabel}</Badge>
                    </div>
                    <PlanActions
                        rows={planRows}
                        selectedActionIds={selectedActionIds}
                        onToggleAction={handleToggleAction}
                    />
                </div>
                <div className="space-y-4">
                    <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                            <CheckSquare size={18} />
                            Apply Gate
                        </h2>
                        <div className="mb-4 grid grid-cols-2 gap-2 text-sm">
                            <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                                <p className="text-xs uppercase tracking-wider text-gray-600">Actions</p>
                                <p className="mt-1 font-mono text-lg text-white">{selectedActionIds.length}</p>
                            </div>
                            <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                                <p className="text-xs uppercase tracking-wider text-gray-600">Blocked</p>
                                <p className="mt-1 font-mono text-lg text-white">{planSummary.blockedCount}</p>
                            </div>
                        </div>
                        <label className="mb-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-950/10 p-3 text-sm text-amber-100">
                            <input
                                type="checkbox"
                                checked={confirmApply}
                                onChange={(event) => setConfirmApply(event.target.checked)}
                                className="mt-1 h-4 w-4 rounded border-amber-600 bg-gray-900 text-amber-500"
                            />
                            <span>Quarantine selected cache targets and keep a restore manifest.</span>
                        </label>
                        <button
                            onClick={handleApply}
                            disabled={isApplying || !canApply}
                            className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isApplying ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
                            Apply Quarantine
                        </button>
                    </section>
                    <OperationPanel
                        summary={operationSummary}
                        onRefresh={handleOperationStatus}
                        onRestore={handleRestore}
                        busy={isRestoring}
                    />
                </div>
            </section>

            <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h2 className="text-lg font-semibold text-white">Targets</h2>
                        <span className="w-fit rounded-md border border-gray-700 bg-black/20 px-2 py-1 text-xs uppercase text-gray-300">
                            {summary.statusLabel}
                        </span>
                    </div>
                    <TargetTable rows={rows} />
                </div>

                <div className="space-y-4">
                    <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-3 text-lg font-semibold text-white">Root</h2>
                        <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                            {summary.rootPath || simsPath || DEFAULT_SIMS_PATH}
                        </p>
                    </section>
                    <MessageList
                        icon={CheckCircle2}
                        title="Recommendations"
                        messages={status?.recommendations || []}
                        tone="blue"
                    />
                    <MessageList
                        icon={AlertTriangle}
                        title="Warnings"
                        messages={status?.warnings || []}
                        tone="red"
                    />
                </div>
            </section>

            <FilePicker
                isOpen={showFilePicker}
                onClose={() => setShowFilePicker(false)}
                onSelect={setSimsPath}
                initialPath={simsPath || DEFAULT_SIMS_PATH}
            />
        </div>
    );
}

export default CacheDoctor;
