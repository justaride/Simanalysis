import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    ClipboardList,
    RotateCcw,
    FolderOpen,
    Loader2,
    Search,
    ShieldCheck,
    Wrench,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import {
    getFixActionAffordance,
    groupActionsBySeverity,
    summarizeFixPlan,
    summarizeFixSession,
} from './fixPlanModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

const GROUPS = [
    { key: 'high', title: 'High Priority', tone: 'red' },
    { key: 'medium', title: 'Review Next', tone: 'amber' },
    { key: 'low', title: 'Maintenance', tone: 'blue' },
    { key: 'unknown', title: 'Unclassified', tone: 'gray' },
];

function StatTile({ label, value, tone = 'gray' }) {
    const tones = {
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
        red: 'border-red-500/30 bg-red-950/20 text-red-200',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-200',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
        </div>
    );
}

function ActionCard({ action, isApplying, onApply }) {
    const affordance = getFixActionAffordance(action);
    const badgeClass =
        affordance.tone === 'emerald'
            ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200'
            : 'border-cyan-500/30 bg-cyan-950/20 text-cyan-200';

    return (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <p className="break-words font-medium text-white">{action.title}</p>
                    <p className="mt-2 text-sm leading-6 text-gray-400">{action.body}</p>
                </div>
                <span className={`w-fit rounded-md border px-2 py-1 text-xs uppercase ${badgeClass}`}>
                    {affordance.badge}
                </span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <span className="rounded-md bg-gray-800 px-2 py-1 uppercase text-gray-300">
                    {action.kind?.replaceAll('_', ' ') || 'fix candidate'}
                </span>
                <span className="rounded-md bg-gray-800 px-2 py-1 text-gray-300">
                    {action.proposed_operation || 'review'}
                </span>
                <span className="rounded-md bg-gray-800 px-2 py-1 text-gray-300">
                    {action.target_paths?.length || 0} path(s)
                </span>
            </div>
            {(action.target_paths || []).length > 0 && (
                <div className="mt-4 space-y-2">
                    {(action.target_paths || []).slice(0, 4).map((path) => (
                        <p key={path} className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-500">
                            {path}
                        </p>
                    ))}
                    {action.target_paths.length > 4 && (
                        <p className="text-xs text-gray-500">+{action.target_paths.length - 4} more path(s)</p>
                    )}
                </div>
            )}
            {affordance.label && (
                <button
                    type="button"
                    onClick={() => onApply?.(affordance.actionKind)}
                    disabled={isApplying}
                    className="mt-4 inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-gray-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isApplying ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                    {affordance.label}
                </button>
            )}
        </div>
    );
}

function ActionGroup({ group, actions, isApplying, onApply }) {
    if (!actions.length) return null;
    const visibleActions = actions.slice(0, 50);

    const toneClass = {
        red: 'border-red-500/30 text-red-200',
        amber: 'border-amber-500/30 text-amber-200',
        blue: 'border-blue-500/30 text-blue-200',
        gray: 'border-gray-700 text-gray-300',
    }[group.tone];

    return (
        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className={`rounded-md border px-2 py-1 text-sm font-semibold ${toneClass}`}>
                    {group.title}
                </h2>
                <span className="text-sm text-gray-500">{actions.length}</span>
            </div>
            <div className="space-y-3">
                {visibleActions.map((action) => (
                    <ActionCard
                        key={action.action_id || action.title}
                        action={action}
                        isApplying={isApplying}
                        onApply={onApply}
                    />
                ))}
            </div>
            {actions.length > visibleActions.length && (
                <p className="mt-3 text-sm text-gray-500">+{actions.length - visibleActions.length} more action(s)</p>
            )}
        </section>
    );
}

function Fixes() {
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [showPicker, setShowPicker] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [session, setSession] = useState(null);
    const [isScanning, setIsScanning] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const [isRestoring, setIsRestoring] = useState(false);

    const summary = useMemo(() => summarizeFixPlan(result), [result]);
    const grouped = useMemo(() => groupActionsBySeverity(result?.actions || []), [result]);
    const sessionSummary = useMemo(() => summarizeFixSession(session), [session]);

    const handlePlan = () => {
        setError(null);
        setActionError(null);
        setSession(null);
        setIsScanning(true);
        api.planFixes(simsPath, {
            onComplete: (data) => {
                setResult(data);
                setIsScanning(false);
            },
            onError: (message) => {
                setError(message);
                setIsScanning(false);
            },
            onDone: () => setIsScanning(false),
        });
    };

    const handleApply = (actionKind) => {
        if (actionKind !== 'cache_cleanup') return;
        const confirmed = window.confirm(
            'Move supported cache files into a Simanalysis backup folder? The Sims 4 must be closed.',
        );
        if (!confirmed) return;

        setActionError(null);
        setIsApplying(true);
        api.applyFix(simsPath, actionKind, {
            onComplete: (data) => {
                setSession(data);
                setIsApplying(false);
            },
            onError: (message) => {
                setActionError(message);
                setIsApplying(false);
            },
            onDone: () => setIsApplying(false),
        });
    };

    const handleRestore = () => {
        if (!sessionSummary.manifestPath) return;
        const confirmed = window.confirm('Restore the cache files from this Simanalysis manifest?');
        if (!confirmed) return;

        setActionError(null);
        setIsRestoring(true);
        api.restoreFix(sessionSummary.manifestPath, {
            onComplete: (data) => {
                setSession(data);
                setIsRestoring(false);
            },
            onError: (message) => {
                setActionError(message);
                setIsRestoring(false);
            },
            onDone: () => setIsRestoring(false),
        });
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div className="flex items-center gap-3">
                    <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-3 text-emerald-200">
                        <Wrench size={26} />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white">Fixes</h1>
                        <p className="mt-1 text-sm text-gray-400">Manifest-backed cleanup and install-risk plan</p>
                    </div>
                </div>
                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                    <div className="min-w-0 md:w-[34rem]">
                        <label htmlFor="fixes-sims-path" className="mb-2 block text-sm font-medium text-gray-300">
                            Sims 4 folder
                        </label>
                        <div className="flex rounded-lg border border-gray-700 bg-gray-950/60">
                            <input
                                id="fixes-sims-path"
                                value={simsPath}
                                onChange={(event) => setSimsPath(event.target.value)}
                                className="min-w-0 flex-1 rounded-l-lg bg-transparent px-3 py-2 font-mono text-sm text-white outline-none"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPicker(true)}
                                className="border-l border-gray-700 px-3 text-gray-300 hover:text-white"
                                title="Choose folder"
                            >
                                <FolderOpen size={18} />
                            </button>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={handlePlan}
                        disabled={isScanning || !simsPath.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 font-medium text-gray-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isScanning ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
                        Plan Fixes
                    </button>
                </div>
            </div>

            <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4 text-cyan-100">
                <div className="flex items-start gap-3">
                    <ShieldCheck size={20} className="mt-0.5 shrink-0" />
                    <p className="text-sm leading-6">
                        Cache cleanup can be moved to a manifest-backed backup. Duplicate, package, and install-risk actions remain review-only.
                    </p>
                </div>
            </div>

            <AnimatePresence>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-red-200"
                    >
                        <div className="flex items-center gap-2">
                            <AlertTriangle size={18} />
                            <p>{error}</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {actionError && (
                    <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-red-200"
                    >
                        <div className="flex items-center gap-2">
                            <AlertTriangle size={18} />
                            <p>{actionError}</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {session && (
                <section className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4 text-emerald-100">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <ShieldCheck size={18} />
                                <h2 className="text-sm font-semibold uppercase tracking-wider">
                                    Cache cleanup {sessionSummary.status}
                                </h2>
                            </div>
                            <p className="mt-3 text-sm text-emerald-100/80">
                                {sessionSummary.recordCount} item(s) recorded in the fix manifest.
                            </p>
                            {sessionSummary.manifestPath && (
                                <p className="mt-3 break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-emerald-100/70">
                                    {sessionSummary.manifestPath}
                                </p>
                            )}
                        </div>
                        {sessionSummary.canRestore && (
                            <button
                                type="button"
                                onClick={handleRestore}
                                disabled={isRestoring}
                                className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-400/40 px-3 py-2 text-sm font-medium text-emerald-50 transition hover:bg-emerald-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {isRestoring ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
                                Restore Cache
                            </button>
                        )}
                    </div>
                </section>
            )}

            {result && (
                <>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                        <StatTile label="Actions" value={summary.actions} tone="emerald" />
                        <StatTile label="High" value={summary.high} tone="red" />
                        <StatTile label="Medium" value={summary.medium} tone="amber" />
                        <StatTile label="Low" value={summary.low} tone="blue" />
                        <StatTile label="Warnings" value={summary.warnings} />
                        <StatTile label="Blockers" value={summary.blockers} />
                    </div>

                    {(result.warnings || []).length > 0 && (
                        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-amber-200">
                            {(result.warnings || []).map((warning) => (
                                <p key={warning}>{warning}</p>
                            ))}
                        </div>
                    )}

                    {summary.actions === 0 ? (
                        <div className="rounded-xl border border-gray-800 bg-gray-900/35 p-8 text-center text-gray-500">
                            <ClipboardList size={34} className="mx-auto mb-3 text-gray-600" />
                            <p>No fix candidates found in the read-only plan.</p>
                        </div>
                    ) : (
                        <div className="grid gap-4 xl:grid-cols-2">
                            {GROUPS.map((group) => (
                                <ActionGroup
                                    key={group.key}
                                    group={group}
                                    actions={grouped[group.key]}
                                    isApplying={isApplying}
                                    onApply={handleApply}
                                />
                            ))}
                        </div>
                    )}
                </>
            )}

            {!result && !isScanning && (
                <div className="rounded-xl border border-gray-800 bg-gray-900/35 p-8 text-center text-gray-500">
                    <ClipboardList size={34} className="mx-auto mb-3 text-gray-600" />
                    <p>No fix plan loaded.</p>
                </div>
            )}

            <FilePicker
                isOpen={showPicker}
                onClose={() => setShowPicker(false)}
                onSelect={setSimsPath}
                initialPath={simsPath}
                selectDirectory
            />
        </div>
    );
}

export default Fixes;
