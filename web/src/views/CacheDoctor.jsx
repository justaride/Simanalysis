import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    FolderOpen,
    HardDrive,
    Loader2,
    RefreshCw,
    ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import {
    summarizeCacheStatus,
    toCacheTargetRows,
} from './cacheDoctorModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

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

function CacheDoctor() {
    const [simsPath, setSimsPath] = useProfileDefaultPath('cachePath', {
        storageKey: 'cache-doctor-root-path',
        fallback: DEFAULT_SIMS_PATH,
    });
    const [showFilePicker, setShowFilePicker] = useState(false);
    const [status, setStatus] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const summary = useMemo(() => summarizeCacheStatus(status || {}), [status]);
    const rows = useMemo(() => toCacheTargetRows(status || {}), [status]);

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
