import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    Archive,
    ClipboardList,
    Files,
    FileWarning,
    FolderOpen,
    Loader2,
    ShieldCheck,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { flattenCleanupActions, summarizeCleanupPlan } from './cleanupModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

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

function ActionCard({ action }) {
    return (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
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

function Cleanup() {
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [dbPath, setDbPath] = useState('');
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showDbPicker, setShowDbPicker] = useState(false);
    const [plan, setPlan] = useState(null);
    const [error, setError] = useState(null);
    const [progress, setProgress] = useState(null);
    const [busy, setBusy] = useState(false);

    const summary = useMemo(() => summarizeCleanupPlan(plan || {}), [plan]);
    const actions = useMemo(() => flattenCleanupActions(plan || {}), [plan]);

    const runPlan = () => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            return;
        }

        setBusy(true);
        setError(null);
        setProgress(null);
        api.cleanupPlan(simsPath.trim(), {
            onProgress: (nextProgress) => setProgress(nextProgress),
            onComplete: (data) => {
                setPlan(data);
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
                            Read-only review
                        </span>
                        <span className="rounded-md border border-gray-700 px-2 py-1 text-gray-400">
                            Inventory ledger
                        </span>
                    </div>
                </motion.header>

                <section className="glass-card min-w-0 p-5">
                    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
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
                            </div>

                            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                    <FileWarning size={20} className="text-amber-300" />
                                    Review Actions
                                </h2>
                                {actions.length ? (
                                    <div className="space-y-3">
                                        {actions.map((action) => (
                                            <ActionCard key={action.id || `${action.source}-${action.destination}`} action={action} />
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
            </div>
        </div>
    );
}

export default Cleanup;
