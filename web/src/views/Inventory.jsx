import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    Archive,
    Boxes,
    Clock3,
    Database,
    FileClock,
    FileSearch,
    FolderOpen,
    History,
    Loader2,
    Package,
    RefreshCw,
    Search,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { api } from '../api';
import FilePicker from '../components/FilePicker';
import {
    latestHistoryScan,
    summarizeInventoryScan,
    toInventoryEventRows,
    toInventoryFileRows,
} from './inventoryModel';

const FILE_ROW_LIMIT = 250;

const STATUS_OPTIONS = [
    ['all', 'All changes'],
    ['added', 'Added'],
    ['modified', 'Modified'],
    ['moved', 'Moved'],
    ['removed', 'Removed'],
    ['unchanged', 'Unchanged'],
];

function shortHash(hash) {
    return hash ? `${hash.slice(0, 10)}...` : 'none';
}

function statusClass(status) {
    switch (status) {
        case 'added':
            return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200';
        case 'modified':
            return 'border-amber-500/40 bg-amber-500/10 text-amber-200';
        case 'moved':
        case 'moved_source':
            return 'border-sky-500/40 bg-sky-500/10 text-sky-200';
        case 'removed':
            return 'border-rose-500/40 bg-rose-500/10 text-rose-200';
        case 'unchanged':
            return 'border-gray-600 bg-gray-800 text-gray-300';
        default:
            return 'border-gray-600 bg-gray-800 text-gray-300';
    }
}

function StatTile({ icon: Icon, label, value, detail, tone = 'blue' }) {
    const tones = {
        blue: 'bg-blue-500/15 text-blue-300',
        amber: 'bg-amber-500/15 text-amber-300',
        green: 'bg-emerald-500/15 text-emerald-300',
        slate: 'bg-gray-700 text-gray-300',
    };

    return (
        <div className="glass-card p-4 min-w-0">
            <div className="flex items-center gap-3">
                <div className={`rounded-lg p-2 ${tones[tone] || tones.blue}`}>
                    <Icon size={20} />
                </div>
                <div className="min-w-0">
                    <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
                    <div className="text-2xl font-semibold text-white">{value}</div>
                    {detail && <div className="truncate text-xs text-gray-500">{detail}</div>}
                </div>
            </div>
        </div>
    );
}

function HistoryList({ historyResult }) {
    const scans = Array.isArray(historyResult?.scans) ? historyResult.scans : [];
    if (scans.length === 0) {
        return (
            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 text-sm text-gray-500">
                No recorded scan history for this folder.
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {scans.slice(0, 6).map((scan) => (
                <div
                    key={scan.scan_id}
                    className="grid gap-3 rounded-lg border border-gray-700 bg-gray-900/50 p-3 text-sm md:grid-cols-[minmax(0,1fr)_auto]"
                >
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-white">Scan {scan.scan_id}</span>
                            <span className="text-gray-500">{scan.status}</span>
                        </div>
                        <div className="truncate text-xs text-gray-500">{scan.completed_at || scan.started_at}</div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded-md border border-gray-700 px-2 py-1 text-gray-300">
                            {scan.files_total} files
                        </span>
                        <span className="rounded-md border border-emerald-500/30 px-2 py-1 text-emerald-200">
                            +{scan.added}
                        </span>
                        <span className="rounded-md border border-amber-500/30 px-2 py-1 text-amber-200">
                            {scan.modified} modified
                        </span>
                        <span className="rounded-md border border-sky-500/30 px-2 py-1 text-sky-200">
                            {scan.moved} moved
                        </span>
                    </div>
                </div>
            ))}
        </div>
    );
}

function EventList({ eventRows }) {
    if (eventRows.length === 0) {
        return (
            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 text-sm text-gray-500">
                No changed file events in the latest scan.
            </div>
        );
    }

    return (
        <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
            {eventRows.map((event) => (
                <div
                    key={`${event.changeStatus}:${event.relativePath}:${event.previousRelativePath || ''}`}
                    className="rounded-lg border border-gray-700 bg-gray-900/50 p-3"
                >
                    <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-md border px-2 py-1 text-xs ${statusClass(event.changeStatus)}`}>
                            {event.changeLabel}
                        </span>
                        <span className="min-w-0 break-all text-sm font-medium text-white">
                            {event.relativePath}
                        </span>
                    </div>
                    {event.previousRelativePath && (
                        <div className="mt-2 break-all text-xs text-gray-500">
                            Previous: {event.previousRelativePath}
                        </div>
                    )}
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
                        <span>{event.sizeLabel}</span>
                        <span>{shortHash(event.sha256)}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}

function Inventory() {
    const [simsPath, setSimsPath] = useState(() => localStorage.getItem('inventory-root-path') || '');
    const [showFilePicker, setShowFilePicker] = useState(false);
    const [scanResult, setScanResult] = useState(null);
    const [historyResult, setHistoryResult] = useState(null);
    const [eventResult, setEventResult] = useState(null);
    const [includeUnchanged, setIncludeUnchanged] = useState(false);
    const [query, setQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [isScanning, setIsScanning] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [isLoadingEvents, setIsLoadingEvents] = useState(false);
    const [error, setError] = useState(null);

    const summary = useMemo(() => summarizeInventoryScan(scanResult || {}), [scanResult]);
    const fileRows = useMemo(() => toInventoryFileRows(scanResult || {}), [scanResult]);
    const eventRows = useMemo(() => toInventoryEventRows(eventResult || {}), [eventResult]);
    const latestScan = useMemo(() => latestHistoryScan(historyResult || {}), [historyResult]);

    const filteredRows = useMemo(() => {
        const needle = query.trim().toLowerCase();
        return fileRows.filter((row) => {
            const matchesQuery = !needle
                || row.relativePath.toLowerCase().includes(needle)
                || row.kindLabel.toLowerCase().includes(needle)
                || row.sha256.toLowerCase().includes(needle);
            const matchesStatus = statusFilter === 'all' || row.changeStatus === statusFilter;
            return matchesQuery && matchesStatus;
        });
    }, [fileRows, query, statusFilter]);

    const visibleRows = filteredRows.slice(0, FILE_ROW_LIMIT);
    const hiddenRowCount = Math.max(0, filteredRows.length - visibleRows.length);

    const fetchHistory = (path) => {
        const target = (path || simsPath).trim();
        if (!target) return;

        setIsLoadingHistory(true);
        api.inventoryHistory(target, {
            onComplete: (result) => {
                setHistoryResult(result);
                setIsLoadingHistory(false);
            },
            onError: (message) => {
                setIsLoadingHistory(false);
                toast.error(`Inventory history failed: ${message}`);
            },
        });
    };

    const fetchEvents = (path, includeAll = includeUnchanged) => {
        const target = (path || simsPath).trim();
        if (!target) return;

        setIsLoadingEvents(true);
        api.inventoryFileEvents(target, {
            onComplete: (result) => {
                setEventResult(result);
                setIsLoadingEvents(false);
            },
            onError: (message) => {
                setIsLoadingEvents(false);
                toast.error(`Inventory events failed: ${message}`);
            },
        }, { includeUnchanged: includeAll });
    };

    const handleScan = () => {
        const target = simsPath.trim();
        if (!target) {
            toast.error('Choose a Sims 4 folder first');
            return;
        }

        localStorage.setItem('inventory-root-path', target);
        setError(null);
        setIsScanning(true);
        const toastId = toast.loading('Scanning inventory ledger...');

        api.scanInventory(target, {
            onComplete: (result) => {
                setScanResult(result);
                setIsScanning(false);
                toast.success(`Inventory scan complete: ${result.files_total || 0} files recorded.`, {
                    id: toastId,
                });
                fetchHistory(target);
                fetchEvents(target, includeUnchanged);
            },
            onError: (message) => {
                setError(message);
                setIsScanning(false);
                toast.error(`Inventory scan failed: ${message}`, { id: toastId });
            },
        });
    };

    const handleToggleEvents = (checked) => {
        setIncludeUnchanged(checked);
        if (eventResult || scanResult) {
            fetchEvents(simsPath, checked);
        }
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <motion.header
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6"
            >
                <h1 className="flex items-center gap-3 text-3xl font-bold text-white">
                    <span className="rounded-lg bg-emerald-500/15 p-2 text-emerald-300">
                        <Database size={28} />
                    </span>
                    Inventory Ledger
                </h1>
                <p className="mt-2 text-gray-400">Read-only scan history for the selected Sims 4 folder.</p>
            </motion.header>

            <section className="mb-6 rounded-lg border border-gray-700 bg-gray-900/60 p-4">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
                    <div className="flex min-w-0 gap-2">
                        <input
                            id="inventory-root-path"
                            name="inventory-root-path"
                            type="text"
                            value={simsPath}
                            onChange={(event) => setSimsPath(event.target.value)}
                            placeholder="/path/to/The Sims 4"
                            className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white placeholder:text-gray-600 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        />
                        <button
                            type="button"
                            onClick={() => setShowFilePicker(true)}
                            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-300 transition hover:border-gray-500 hover:text-white"
                            title="Choose folder"
                        >
                            <FolderOpen size={18} />
                        </button>
                    </div>
                    <button
                        type="button"
                        onClick={handleScan}
                        disabled={isScanning}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isScanning ? <Loader2 size={18} className="animate-spin" /> : <FileSearch size={18} />}
                        Scan Ledger
                    </button>
                    <button
                        type="button"
                        onClick={() => fetchHistory(simsPath)}
                        disabled={isLoadingHistory || !simsPath.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-gray-200 transition hover:border-gray-500 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isLoadingHistory ? <Loader2 size={18} className="animate-spin" /> : <History size={18} />}
                        History
                    </button>
                    <button
                        type="button"
                        onClick={() => fetchEvents(simsPath)}
                        disabled={isLoadingEvents || !simsPath.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-gray-200 transition hover:border-gray-500 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isLoadingEvents ? <Loader2 size={18} className="animate-spin" /> : <RefreshCw size={18} />}
                        Events
                    </button>
                </div>
                {error && (
                    <div className="mt-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                        {error}
                    </div>
                )}
            </section>

            <FilePicker
                isOpen={showFilePicker}
                onClose={() => setShowFilePicker(false)}
                onSelect={(path) => setSimsPath(path)}
                initialPath={simsPath || '~/Documents/Electronic Arts/The Sims 4'}
                selectDirectory={true}
                title="Select Sims 4 Folder"
            />

            {scanResult ? (
                <div className="space-y-6">
                    <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <StatTile icon={Archive} label="Files" value={summary.filesTotal} detail="Latest snapshot" />
                        <StatTile icon={Package} label="Packages" value={summary.packagesTotal} detail={`${summary.resourcesTotal} resources`} tone="green" />
                        <StatTile icon={FileClock} label="Changed" value={summary.changedTotal} detail={`${summary.unchanged} unchanged`} tone="amber" />
                        <StatTile icon={AlertTriangle} label="Parse Warnings" value={summary.packageParseErrors} detail={`${summary.warnings.length} scan warnings`} tone="slate" />
                    </section>

                    <section className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,0.8fr)]">
                        <div className="glass-card min-w-0 p-5">
                            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                <div>
                                    <h2 className="text-xl font-semibold text-white">Snapshot Files</h2>
                                    <div className="mt-1 break-all text-xs text-gray-500">
                                        Scan {summary.scanId} · {summary.rootPath}
                                    </div>
                                </div>
                                <div className="flex flex-col gap-2 sm:flex-row">
                                    <div className="relative min-w-[220px]">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                                        <input
                                            id="inventory-file-search"
                                            name="inventory-file-search"
                                            type="text"
                                            value={query}
                                            onChange={(event) => setQuery(event.target.value)}
                                            placeholder="Search files"
                                            className="w-full rounded-lg border border-gray-700 bg-gray-950 py-2 pl-9 pr-3 text-sm text-white placeholder:text-gray-600 focus:border-emerald-500 focus:outline-none"
                                        />
                                    </div>
                                    <select
                                        id="inventory-status-filter"
                                        name="inventory-status-filter"
                                        value={statusFilter}
                                        onChange={(event) => setStatusFilter(event.target.value)}
                                        className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
                                    >
                                        {STATUS_OPTIONS.map(([value, label]) => (
                                            <option key={value} value={value}>{label}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="overflow-hidden rounded-lg border border-gray-700">
                                <div className="grid grid-cols-[minmax(180px,1fr)_110px_110px_120px_110px] gap-3 bg-gray-800 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-400 max-lg:hidden">
                                    <div>Path</div>
                                    <div>Kind</div>
                                    <div>Change</div>
                                    <div>Package</div>
                                    <div>Size</div>
                                </div>
                                <div className="max-h-[520px] overflow-y-auto">
                                    {visibleRows.map((row) => (
                                        <div
                                            key={`${row.changeStatus}:${row.relativePath}`}
                                            className="grid gap-2 border-t border-gray-800 px-4 py-3 text-sm lg:grid-cols-[minmax(180px,1fr)_110px_110px_120px_110px] lg:items-center lg:gap-3"
                                        >
                                            <div className="min-w-0">
                                                <div className="break-all font-medium text-white">{row.relativePath}</div>
                                                <div className="mt-1 text-xs text-gray-500">{shortHash(row.sha256)}</div>
                                            </div>
                                            <div className="text-gray-300">{row.kindLabel}</div>
                                            <div>
                                                <span className={`inline-flex rounded-md border px-2 py-1 text-xs ${statusClass(row.changeStatus)}`}>
                                                    {row.changeLabel}
                                                </span>
                                            </div>
                                            <div className="text-gray-300">
                                                {row.packageLabel}
                                                {row.resourceCount !== null && (
                                                    <span className="ml-1 text-gray-500">({row.resourceCount})</span>
                                                )}
                                            </div>
                                            <div className="text-gray-300">{row.sizeLabel}</div>
                                        </div>
                                    ))}
                                    {visibleRows.length === 0 && (
                                        <div className="px-4 py-8 text-center text-sm text-gray-500">
                                            No files match the current filters.
                                        </div>
                                    )}
                                </div>
                            </div>
                            {hiddenRowCount > 0 && (
                                <div className="mt-3 text-sm text-gray-500">
                                    Showing {visibleRows.length} of {filteredRows.length} matching files.
                                </div>
                            )}
                        </div>

                        <aside className="space-y-4 min-w-0">
                            <div className="glass-card p-5">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                                        <Clock3 size={18} />
                                        Recent Scans
                                    </h2>
                                    {latestScan && (
                                        <span className="rounded-md border border-gray-700 px-2 py-1 text-xs text-gray-400">
                                            Latest {latestScan.scan_id}
                                        </span>
                                    )}
                                </div>
                                <HistoryList historyResult={historyResult} />
                            </div>

                            <div className="glass-card p-5">
                                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                                    <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                                        <Boxes size={18} />
                                        Latest Events
                                    </h2>
                                    <label className="inline-flex items-center gap-2 text-xs text-gray-400">
                                        <input
                                            id="inventory-include-unchanged"
                                            name="inventory-include-unchanged"
                                            type="checkbox"
                                            checked={includeUnchanged}
                                            onChange={(event) => handleToggleEvents(event.target.checked)}
                                            className="h-4 w-4 rounded border-gray-700 bg-gray-900 text-emerald-500 focus:ring-emerald-500/30"
                                        />
                                        Include unchanged
                                    </label>
                                </div>
                                <EventList eventRows={eventRows} />
                            </div>

                            {summary.warnings.length > 0 && (
                                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                                    <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-100">
                                        <AlertTriangle size={16} />
                                        Scan Warnings
                                    </h2>
                                    <ul className="space-y-1 text-sm text-amber-100/80">
                                        {summary.warnings.map((warning) => (
                                            <li key={warning} className="break-all">{warning}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </aside>
                    </section>
                </div>
            ) : (
                <div className="glass-card flex min-h-[360px] flex-col items-center justify-center p-8 text-center">
                    <div className="mb-5 rounded-lg bg-emerald-500/15 p-4 text-emerald-300">
                        <Database size={36} />
                    </div>
                    <h2 className="text-2xl font-semibold text-white">No inventory snapshot loaded</h2>
                    <p className="mt-2 max-w-md text-gray-400">
                        Select the Sims 4 folder to record a read-only ledger snapshot.
                    </p>
                </div>
            )}
        </div>
    );
}

export default Inventory;
