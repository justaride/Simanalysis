import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    AlertTriangle,
    Clock,
    FileWarning,
    FolderOpen,
    History,
    Loader2,
    RadioTower,
    ShieldCheck,
    Square,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import FilePicker from '../components/FilePicker';
import { useLiveMonitor } from '../context/LiveMonitorContext';
import { describeRecommendation, statusText, summarizeMonitorEvent } from './liveMonitorModel';

function toneClasses(tone) {
    return {
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-100',
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
    }[tone] || 'border-gray-800 bg-gray-900/50 text-gray-300';
}

function formatTimestamp(value) {
    if (!value) return 'No timestamp';
    return new Intl.DateTimeFormat(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    }).format(new Date(value));
}

function StatTile({ label, value, tone = 'gray' }) {
    return (
        <div className={`rounded-xl border p-4 ${toneClasses(tone)}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-2 break-words text-2xl font-semibold text-white">{value}</p>
        </div>
    );
}

function EventCard({ event, onOpenTreatment }) {
    if (!event) {
        return (
            <section className="flex min-h-[360px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-gray-900/40 p-8 text-center">
                <RadioTower className="mb-4 text-gray-600" size={52} />
                <h2 className="text-xl font-semibold text-white">No new crash evidence yet</h2>
                <p className="mt-2 max-w-md text-sm text-gray-500">
                    Start monitoring, then test in The Sims 4. New crash logs will appear here.
                </p>
            </section>
        );
    }

    const summary = summarizeMonitorEvent(event.data);
    const recommendation = describeRecommendation(summary.recommendation);

    return (
        <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-xl border p-5 ${toneClasses(recommendation.tone)}`}
        >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-80">
                        <Clock size={14} />
                        Latest event {formatTimestamp(event.receivedAt)}
                    </p>
                    <h2 className="mt-3 text-xl font-semibold text-white">{recommendation.title}</h2>
                    <p className="mt-2 max-w-3xl text-sm opacity-90">{recommendation.body}</p>
                </div>
                {recommendation.primaryAction === 'open_treatment' && (
                    <button
                        onClick={onOpenTreatment}
                        className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white transition-colors hover:bg-emerald-500 sm:w-auto"
                    >
                        <ShieldCheck size={17} />
                        Open Treatment
                    </button>
                )}
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatTile label="Changed Logs" value={summary.changedLogNames.length} tone="blue" />
                <StatTile label="Script Active" value={summary.scriptActive} tone={summary.scriptActive ? 'amber' : 'gray'} />
                <StatTile label="UI Active" value={summary.uiActive} tone={summary.uiActive ? 'amber' : 'gray'} />
                <StatTile
                    label="Treatment Candidates"
                    value={summary.candidateCount}
                    tone={summary.candidateCount ? 'emerald' : 'gray'}
                />
            </div>

            <div className="mt-5">
                <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-80">
                    <FileWarning size={14} />
                    Changed crash logs
                </p>
                <div className="flex flex-wrap gap-2">
                    {summary.changedLogNames.map((name) => (
                        <span
                            key={name}
                            className="max-w-full truncate rounded-lg border border-gray-700 bg-black/20 px-3 py-1 font-mono text-xs text-gray-200"
                            title={name}
                        >
                            {name}
                        </span>
                    ))}
                </div>
            </div>
        </motion.section>
    );
}

function HistoryList({ history }) {
    if (!history.length) {
        return (
            <p className="rounded-lg border border-gray-800 bg-gray-950/40 p-4 text-sm text-gray-500">
                This monitor run has not recorded any changed crash logs.
            </p>
        );
    }

    return (
        <div className="space-y-3">
            {history.map((event) => {
                const summary = summarizeMonitorEvent(event.data);
                const recommendation = describeRecommendation(summary.recommendation);
                return (
                    <div key={event.id} className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0">
                                <p className="font-medium text-white">{recommendation.title}</p>
                                <p className="mt-1 text-sm text-gray-500">{formatTimestamp(event.receivedAt)}</p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {summary.changedLogNames.map((name) => (
                                        <span
                                            key={name}
                                            className="max-w-full truncate rounded bg-black/30 px-2 py-1 font-mono text-xs text-gray-400"
                                            title={name}
                                        >
                                            {name}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            <span className={`w-fit rounded-md border px-2 py-1 text-xs uppercase ${toneClasses(recommendation.tone)}`}>
                                {summary.recommendation}
                            </span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function LiveMonitor() {
    const navigate = useNavigate();
    const monitor = useLiveMonitor();
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showModsPicker, setShowModsPicker] = useState(false);
    const watchedCount = monitor.progress?.total || monitor.latestEvent?.data?.watched_log_count || 0;

    const openTreatment = () => {
        navigate('/treatment', {
            state: { simsPath: monitor.simsPath, modsPath: monitor.modsPath },
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
                            <RadioTower size={28} />
                        </span>
                        Live Monitor
                    </h1>
                    <p className="max-w-3xl text-gray-400">
                        Manually watch for new crash logs while you test. Simanalysis stays read-only until you choose Treatment.
                    </p>
                </motion.header>

                <section className="glass-card min-w-0 p-5">
                    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
                        <div className="min-w-0">
                            <label htmlFor="live-monitor-sims-path" className="mb-2 block text-sm font-medium text-gray-300">
                                Sims 4 Folder
                            </label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    id="live-monitor-sims-path"
                                    value={monitor.simsPath}
                                    onChange={(event) => monitor.setSimsPath(event.target.value)}
                                    disabled={monitor.isWatching}
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white disabled:cursor-not-allowed disabled:opacity-60"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    disabled={monitor.isWatching}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    title="Browse for Sims 4 folder"
                                    aria-label="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="min-w-0">
                            <label htmlFor="live-monitor-mods-path" className="mb-2 block text-sm font-medium text-gray-300">
                                Mods Folder
                            </label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    id="live-monitor-mods-path"
                                    value={monitor.modsPath}
                                    onChange={(event) => monitor.setModsPath(event.target.value)}
                                    disabled={monitor.isWatching}
                                    placeholder="Default: Sims 4 folder / Mods"
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
                                />
                                <button
                                    onClick={() => setShowModsPicker(true)}
                                    disabled={monitor.isWatching}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    title="Browse for Mods folder"
                                    aria-label="Browse for Mods folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={monitor.start}
                                disabled={monitor.isWatching || !monitor.simsPath.trim()}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60 lg:w-auto"
                            >
                                {monitor.isWatching ? <Loader2 className="animate-spin" size={18} /> : <RadioTower size={18} />}
                                {monitor.isWatching ? 'Watching' : 'Start'}
                            </button>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={monitor.stop}
                                disabled={!monitor.isWatching}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-gray-700 px-5 font-medium text-gray-200 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 lg:w-auto"
                            >
                                <Square size={16} />
                                Stop
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {monitor.error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                <AlertTriangle className="mt-0.5 shrink-0" size={17} />
                                <span className="break-words">{monitor.error}</span>
                            </motion.div>
                        )}
                        {monitor.progress && !monitor.error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-blue-500/30 bg-blue-950/20 p-3 text-sm text-blue-100"
                            >
                                {monitor.progress.stage || 'Working'} - {monitor.progress.current || 0}/{monitor.progress.total || 0}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                <section className="grid gap-4 md:grid-cols-3">
                    <StatTile label="Status" value={statusText(monitor.status)} tone={monitor.isWatching ? 'blue' : 'gray'} />
                    <StatTile label="Watched Logs" value={watchedCount} tone={watchedCount ? 'blue' : 'gray'} />
                    <StatTile label="Session Events" value={monitor.history.length} tone={monitor.history.length ? 'emerald' : 'gray'} />
                </section>

                <EventCard event={monitor.latestEvent} onOpenTreatment={openTreatment} />

                <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                    <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                            <History size={20} className="text-blue-300" />
                            Session History
                        </h2>
                        <HistoryList history={monitor.history} />
                    </div>

                    <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
                            <ShieldCheck size={20} className="text-emerald-300" />
                            Safety
                        </h2>
                        <p className="text-sm text-gray-400">
                            Live Monitor reads crash logs, runs Doctor, and asks Treatment for a dry-run plan. It does not create a
                            Treatment manifest or move files.
                        </p>
                    </div>
                </section>

                <FilePicker
                    isOpen={showSimsPicker}
                    onClose={() => setShowSimsPicker(false)}
                    onSelect={(path) => monitor.setSimsPath(path)}
                    initialPath={monitor.simsPath}
                    selectDirectory={true}
                />
                <FilePicker
                    isOpen={showModsPicker}
                    onClose={() => setShowModsPicker(false)}
                    onSelect={(path) => monitor.setModsPath(path)}
                    initialPath={monitor.modsPath || monitor.simsPath}
                    selectDirectory={true}
                />
            </div>
        </div>
    );
}

export default LiveMonitor;
