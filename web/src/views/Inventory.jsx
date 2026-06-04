import { useMemo, useState } from 'react';
import {
    Activity,
    AlertTriangle,
    ArrowRightLeft,
    CheckCircle2,
    Database,
    FileArchive,
    FileCode,
    FolderOpen,
    HardDrive,
    Loader2,
    Minus,
    Package,
    Pencil,
    Plus,
    Save,
    XCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';
const EMPTY_SUMMARY = {};
const EMPTY_WARNINGS = [];

function formatNumber(value) {
    return new Intl.NumberFormat().format(Number(value || 0));
}

function formatBytes(value) {
    const bytes = Number(value || 0);
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const amount = bytes / (1024 ** index);
    return `${amount.toFixed(amount >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function compactPath(value) {
    if (!value) return 'Not set';
    return String(value).replace(/^\/Users\/[^/]+/, '~');
}

function statusTone(status) {
    return {
        idle: 'border-gray-800 bg-gray-900/50 text-gray-300',
        running: 'border-blue-500/30 bg-blue-950/20 text-blue-100',
        completed: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
        error: 'border-red-500/30 bg-red-950/20 text-red-100',
    }[status] || 'border-gray-800 bg-gray-900/50 text-gray-300';
}

function MetricTile({ icon: Icon, label, value, tone = 'gray' }) {
    const tones = {
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-100',
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
        rose: 'border-rose-500/30 bg-rose-950/20 text-rose-100',
        violet: 'border-violet-500/30 bg-violet-950/20 text-violet-100',
    };

    return (
        <div className={`rounded-lg border p-4 ${tones[tone] || tones.gray}`}>
            <div className="flex items-start justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-wider opacity-80">{label}</p>
                <Icon size={18} className="shrink-0 opacity-80" />
            </div>
            <p className="mt-3 break-words text-2xl font-semibold text-white">{value}</p>
        </div>
    );
}

function PathLine({ label, value, icon: Icon }) {
    return (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-3">
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                <Icon size={14} />
                {label}
            </p>
            <p className="break-all font-mono text-xs text-gray-300">{compactPath(value)}</p>
        </div>
    );
}

function ChangeStrip({ summary }) {
    const changes = [
        { label: 'Added', value: summary.added_count, icon: Plus, tone: 'emerald' },
        { label: 'Removed', value: summary.removed_count, icon: Minus, tone: 'rose' },
        { label: 'Modified', value: summary.modified_count, icon: Pencil, tone: 'amber' },
        { label: 'Moved', value: summary.moved_count, icon: ArrowRightLeft, tone: 'violet' },
        { label: 'Unchanged', value: summary.unchanged_count, icon: CheckCircle2, tone: 'gray' },
    ];

    return (
        <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-5">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                <Activity size={20} className="text-blue-300" />
                Changes Since Last Scan
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {changes.map((item) => (
                    <MetricTile
                        key={item.label}
                        icon={item.icon}
                        label={item.label}
                        value={formatNumber(item.value)}
                        tone={item.tone}
                    />
                ))}
            </div>
        </section>
    );
}

function ParseHealth({ summary, warnings }) {
    const ok = Number(summary.package_parse_ok_count || 0);
    const errors = Number(summary.package_parse_error_count || 0);
    const warningCount = warnings?.length || 0;

    return (
        <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-5">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                <Package size={20} className="text-emerald-300" />
                Package Parse Health
            </h2>
            <div className="grid gap-3 md:grid-cols-3">
                <MetricTile icon={CheckCircle2} label="Parsed" value={formatNumber(ok)} tone="emerald" />
                <MetricTile icon={XCircle} label="Parse Errors" value={formatNumber(errors)} tone={errors ? 'rose' : 'gray'} />
                <MetricTile icon={AlertTriangle} label="Warnings" value={formatNumber(warningCount)} tone={warningCount ? 'amber' : 'gray'} />
            </div>
            {warningCount > 0 && (
                <div className="mt-4 space-y-2">
                    {warnings.slice(0, 5).map((warning) => (
                        <p key={warning} className="break-words rounded-lg border border-amber-500/20 bg-amber-950/20 p-3 text-sm text-amber-100">
                            {warning}
                        </p>
                    ))}
                    {warningCount > 5 && (
                        <p className="text-sm text-gray-500">+{warningCount - 5} more warning(s)</p>
                    )}
                </div>
            )}
        </section>
    );
}

function Inventory() {
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [exportPath, setExportPath] = useState('');
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [activeRun, setActiveRun] = useState(null);

    const summary = result?.summary || EMPTY_SUMMARY;
    const warnings = result?.warnings || EMPTY_WARNINGS;
    const canStart = simsPath.trim() && status !== 'running';
    const statusLabel = {
        idle: 'Idle',
        running: 'Scanning',
        completed: 'Completed',
        error: 'Error',
    }[status] || 'Idle';

    const mainMetrics = useMemo(() => ([
        { label: 'Files', value: formatNumber(summary.file_count), icon: HardDrive, tone: 'blue' },
        { label: 'Total Size', value: formatBytes(summary.total_size_bytes), icon: Database, tone: 'violet' },
        { label: 'Packages', value: formatNumber(summary.package_count), icon: Package, tone: 'emerald' },
        { label: 'Scripts', value: formatNumber(summary.script_count), icon: FileCode, tone: 'amber' },
        { label: 'Archives', value: formatNumber(summary.archive_count), icon: FileArchive, tone: 'gray' },
        { label: 'Resources', value: formatNumber(summary.resource_count), icon: Activity, tone: 'blue' },
    ]), [summary]);

    const startScan = () => {
        if (!canStart) return;
        setStatus('running');
        setError('');
        setProgress(null);

        const options = {};
        if (exportPath.trim()) {
            options.exportPath = exportPath.trim();
        }

        const run = api.scanInventory(simsPath.trim(), options, {
            onStart: () => {
                setStatus('running');
            },
            onProgress: (event) => {
                setProgress(event);
            },
            onComplete: (payload) => {
                setResult(payload);
                setStatus('completed');
                setProgress(null);
            },
            onError: (message) => {
                setError(message);
                setStatus('error');
                setProgress(null);
            },
            onDone: () => {
                setActiveRun(null);
            },
        });
        setActiveRun(run);
    };

    const cancelScan = () => {
        activeRun?.cancel?.();
        setActiveRun(null);
        setStatus(result ? 'completed' : 'idle');
        setProgress(null);
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
                        <span className="rounded-lg bg-emerald-500/15 p-2 text-emerald-300">
                            <Database size={28} />
                        </span>
                        Inventory
                    </h1>
                    <div className={`w-fit rounded-lg border px-3 py-1 text-sm font-medium ${statusTone(status)}`}>
                        {statusLabel}
                    </div>
                </motion.header>

                <section className="rounded-lg border border-gray-800 bg-gray-900/60 p-5">
                    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
                        <div className="min-w-0">
                            <label htmlFor="inventory-sims-path" className="mb-2 block text-sm font-medium text-gray-300">
                                Sims 4 Folder
                            </label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    id="inventory-sims-path"
                                    value={simsPath}
                                    onChange={(event) => setSimsPath(event.target.value)}
                                    disabled={status === 'running'}
                                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-950/70 px-3 py-2 text-white disabled:cursor-not-allowed disabled:opacity-60"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    disabled={status === 'running'}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    title="Browse for Sims 4 folder"
                                    aria-label="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>

                        <div className="min-w-0">
                            <label htmlFor="inventory-export-path" className="mb-2 block text-sm font-medium text-gray-300">
                                Snapshot Export
                            </label>
                            <input
                                id="inventory-export-path"
                                value={exportPath}
                                onChange={(event) => setExportPath(event.target.value)}
                                disabled={status === 'running'}
                                placeholder="/tmp/simanalysis-inventory.json"
                                className="h-[42px] min-w-0 w-full rounded-lg border border-gray-700 bg-gray-950/70 px-3 py-2 text-white placeholder:text-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                        </div>

                        <div className="flex items-end">
                            <button
                                onClick={startScan}
                                disabled={!canStart}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-5 font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60 xl:w-auto"
                            >
                                {status === 'running' ? <Loader2 className="animate-spin" size={18} /> : <Database size={18} />}
                                {status === 'running' ? 'Scanning' : 'Scan'}
                            </button>
                        </div>

                        <div className="flex items-end">
                            <button
                                onClick={cancelScan}
                                disabled={status !== 'running'}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-gray-700 px-5 font-medium text-gray-200 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 xl:w-auto"
                            >
                                <XCircle size={17} />
                                Cancel
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                <AlertTriangle className="mt-0.5 shrink-0" size={17} />
                                <span className="break-words">{error}</span>
                            </motion.div>
                        )}
                        {progress && !error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-blue-500/30 bg-blue-950/20 p-3 text-sm text-blue-100"
                            >
                                {progress.stage || 'Scanning'} - {progress.current || 0}/{progress.total || 0}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
                    {mainMetrics.map((metric) => (
                        <MetricTile
                            key={metric.label}
                            icon={metric.icon}
                            label={metric.label}
                            value={metric.value}
                            tone={metric.tone}
                        />
                    ))}
                </section>

                <ChangeStrip summary={summary} />

                <section className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
                    <ParseHealth summary={summary} warnings={warnings} />

                    <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                            <Save size={20} className="text-violet-300" />
                            Snapshot
                        </h2>
                        <div className="space-y-3">
                            <PathLine label="Database" value={result?.database_path} icon={Database} />
                            <PathLine label="Export" value={result?.export_path} icon={Save} />
                            <PathLine label="Root" value={summary.root_path || simsPath} icon={FolderOpen} />
                        </div>
                    </section>
                </section>
            </div>

            <FilePicker
                isOpen={showSimsPicker}
                onClose={() => setShowSimsPicker(false)}
                onSelect={(selected) => setSimsPath(selected)}
                initialPath={simsPath}
                selectDirectory
            />
        </div>
    );
}

export default Inventory;
