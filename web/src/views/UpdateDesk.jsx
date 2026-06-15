import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    Archive,
    CheckCircle2,
    ClipboardList,
    Download,
    FileArchive,
    FileJson,
    FolderOpen,
    Loader2,
    Package,
    RefreshCw,
    ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import {
    summarizeUpdateInstallPlan,
    summarizeUpdateDeskStatus,
    toUpdatePlanActionRows,
    toUpdateItemRows,
    toUpdateSignalRows,
} from './updateDeskModel';

const DEFAULT_STAGING_PATH = '~/Downloads/Simanalysis Staging';
const DEFAULT_MODS_PATH = '~/Documents/Electronic Arts/The Sims 4/Mods';
const STORAGE_KEY = 'update-desk-staging-path';
const MODS_STORAGE_KEY = 'update-desk-mods-path';

const toneClasses = {
    blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
    amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
    green: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
    red: 'border-red-500/30 bg-red-950/20 text-red-100',
};

function readStoredPath() {
    if (typeof localStorage === 'undefined') return DEFAULT_STAGING_PATH;
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_STAGING_PATH;
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
                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
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

function sourceTone(row) {
    if (row.sourceStatus === 'bound') return 'green';
    if (row.sourceStatus === 'missing') return 'amber';
    if (row.sourceStatus === 'invalid') return 'red';
    return 'blue';
}

function archiveTone(row) {
    if (row.archiveStatus === 'readable_zip' || row.archiveStatus === 'not_archive') return 'green';
    if (row.archiveStatus === 'unsafe_members' || row.archiveStatus === 'unreadable_zip') return 'red';
    return 'amber';
}

function actionTone(row) {
    if (row.status === 'blocked') return 'red';
    if (row.status === 'review_required') return 'amber';
    if (row.status === 'planned') return 'green';
    return 'blue';
}

function labelize(value) {
    return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function StagedItems({ rows }) {
    if (rows.length === 0) {
        return (
            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5 text-sm text-gray-500">
                No staged update status loaded.
            </div>
        );
    }

    return (
        <>
            <div className="space-y-3 md:hidden">
                {rows.map((row) => (
                    <div key={row.id} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                                <p className="break-words font-medium text-white">{row.name}</p>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                    {row.extension || 'no extension'}
                                </p>
                            </div>
                            <Badge>{row.kindLabel}</Badge>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-gray-400">
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Source</p>
                                <div className="mt-1"><Badge tone={sourceTone(row)}>{row.sourceLabel}</Badge></div>
                            </div>
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Archive</p>
                                <div className="mt-1"><Badge tone={archiveTone(row)}>{row.archiveLabel}</Badge></div>
                            </div>
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Size</p>
                                <p className="mt-1 font-mono text-gray-200">{row.sizeLabel}</p>
                            </div>
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Latest</p>
                                <p className="mt-1 truncate text-gray-200">{row.latestModifiedAt || 'unknown'}</p>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            <div className="hidden overflow-x-auto rounded-xl border border-gray-800 md:block">
                <table className="min-w-full divide-y divide-gray-800 text-sm">
                    <thead className="bg-gray-950/60 text-left text-xs uppercase tracking-wider text-gray-500">
                        <tr>
                            <th className="px-4 py-3 font-medium">Item</th>
                            <th className="px-4 py-3 font-medium">Kind</th>
                            <th className="px-4 py-3 font-medium">Source</th>
                            <th className="px-4 py-3 font-medium">Archive</th>
                            <th className="px-4 py-3 font-medium">Members</th>
                            <th className="px-4 py-3 font-medium">Size</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800 bg-gray-900/30">
                    {rows.map((row) => (
                        <tr key={row.id} className="align-top">
                            <td className="px-4 py-3">
                                <p className="break-words font-medium text-white">{row.name}</p>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                    {row.extension || 'no extension'}
                                </p>
                            </td>
                            <td className="px-4 py-3"><Badge>{row.kindLabel}</Badge></td>
                            <td className="px-4 py-3"><Badge tone={sourceTone(row)}>{row.sourceLabel}</Badge></td>
                            <td className="px-4 py-3"><Badge tone={archiveTone(row)}>{row.archiveLabel}</Badge></td>
                            <td className="px-4 py-3 font-mono text-gray-200">
                                {row.memberCount ?? 'n/a'}
                            </td>
                            <td className="px-4 py-3 font-mono text-gray-200">{row.sizeLabel}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}

function PlanActions({ rows }) {
    if (rows.length === 0) {
        return (
            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5 text-sm text-gray-500">
                No update install plan loaded.
            </div>
        );
    }

    return (
        <>
            <div className="space-y-3 lg:hidden">
                {rows.map((row) => (
                    <div key={row.id} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                                <p className="break-words font-medium text-white">{row.sourceName}</p>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                    {row.sourceRelativePath || row.id}
                                </p>
                            </div>
                            <Badge tone={actionTone(row)}>{row.statusLabel}</Badge>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-gray-400">
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Action</p>
                                <div className="mt-1"><Badge>{row.typeLabel}</Badge></div>
                            </div>
                            <div>
                                <p className="uppercase tracking-wider text-gray-600">Size</p>
                                <p className="mt-1 font-mono text-gray-200">{row.expectedSizeLabel}</p>
                            </div>
                            <div className="col-span-2">
                                <p className="uppercase tracking-wider text-gray-600">Destination</p>
                                <p className="mt-1 break-all font-mono text-gray-200">
                                    {row.destinationRelativePath}
                                </p>
                            </div>
                        </div>
                        {[...row.blockers, ...row.reviewNotes].length > 0 && (
                            <div className="mt-4 flex flex-wrap gap-2">
                                {row.blockers.map((blocker) => (
                                    <Badge key={`blocker-${blocker}`} tone="red">{labelize(blocker)}</Badge>
                                ))}
                                {row.reviewNotes.map((note) => (
                                    <Badge key={`note-${note}`} tone="amber">{labelize(note)}</Badge>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
            <div className="hidden overflow-x-auto rounded-xl border border-gray-800 lg:block">
                <table className="min-w-full divide-y divide-gray-800 text-sm">
                    <thead className="bg-gray-950/60 text-left text-xs uppercase tracking-wider text-gray-500">
                        <tr>
                            <th className="px-4 py-3 font-medium">Action</th>
                            <th className="px-4 py-3 font-medium">Status</th>
                            <th className="px-4 py-3 font-medium">Source</th>
                            <th className="px-4 py-3 font-medium">Destination</th>
                            <th className="px-4 py-3 font-medium">Evidence</th>
                            <th className="px-4 py-3 font-medium">Size</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800 bg-gray-900/30">
                    {rows.map((row) => (
                        <tr key={row.id} className="align-top">
                            <td className="px-4 py-3"><Badge>{row.typeLabel}</Badge></td>
                            <td className="px-4 py-3"><Badge tone={actionTone(row)}>{row.statusLabel}</Badge></td>
                            <td className="px-4 py-3">
                                <p className="break-words font-medium text-white">{row.sourceName}</p>
                                <p className="mt-1 break-all font-mono text-xs text-gray-500">
                                    {row.sourceRelativePath || row.id}
                                </p>
                            </td>
                            <td className="px-4 py-3 break-all font-mono text-xs text-gray-300">
                                {row.destinationRelativePath}
                            </td>
                            <td className="px-4 py-3">
                                <div className="flex flex-wrap gap-2">
                                    <Badge tone={sourceTone(row)}>{row.sourceLabel}</Badge>
                                    <Badge tone={archiveTone(row)}>{row.archiveLabel}</Badge>
                                    {row.blockers.map((blocker) => (
                                        <Badge key={`blocker-${row.id}-${blocker}`} tone="red">
                                            {labelize(blocker)}
                                        </Badge>
                                    ))}
                                    {row.reviewNotes.map((note) => (
                                        <Badge key={`note-${row.id}-${note}`} tone="amber">
                                            {labelize(note)}
                                        </Badge>
                                    ))}
                                </div>
                            </td>
                            <td className="px-4 py-3 font-mono text-gray-200">{row.expectedSizeLabel}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}

function SignalRows({ rows }) {
    if (rows.length === 0) return null;
    return (
        <section className="rounded-xl border border-amber-500/25 bg-amber-950/10 p-5 text-amber-100">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-white">
                <AlertTriangle size={18} />
                Signals
            </h2>
            <div className="space-y-3">
                {rows.map((row) => (
                    <div key={row.id} className="rounded-lg border border-amber-500/20 bg-black/20 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-white">{row.label}</span>
                            <span className="rounded border border-amber-400/20 px-2 py-0.5 text-xs uppercase">
                                {row.severityLabel}
                            </span>
                        </div>
                        <p className="mt-2 text-sm opacity-85">{row.message}</p>
                        {row.location && (
                            <p className="mt-2 break-all font-mono text-xs text-amber-100/70">
                                {row.location}
                            </p>
                        )}
                        {row.detail && (
                            <p className="mt-2 break-all font-mono text-xs text-amber-100/70">
                                {row.detail}
                            </p>
                        )}
                    </div>
                ))}
            </div>
        </section>
    );
}

function UpdateDesk() {
    const [stagingPath, setStagingPath] = useState(readStoredPath);
    const [modsPath, setModsPath] = useProfileDefaultPath('modsPath', {
        storageKey: MODS_STORAGE_KEY,
        fallback: DEFAULT_MODS_PATH,
    });
    const [pickerTarget, setPickerTarget] = useState(null);
    const [status, setStatus] = useState(null);
    const [plan, setPlan] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isPlanning, setIsPlanning] = useState(false);
    const [error, setError] = useState(null);
    const [planError, setPlanError] = useState(null);

    const summary = useMemo(() => summarizeUpdateDeskStatus(status || {}), [status]);
    const itemRows = useMemo(() => toUpdateItemRows(status || {}), [status]);
    const signalRows = useMemo(() => toUpdateSignalRows(status || {}), [status]);
    const planSummary = useMemo(() => summarizeUpdateInstallPlan(plan || {}), [plan]);
    const planRows = useMemo(() => toUpdatePlanActionRows(plan || {}), [plan]);
    const issueCount = summary.warningCount + summary.signalCount;

    const handleStatus = () => {
        const target = stagingPath.trim();
        if (!target) {
            toast.error('Choose a staging folder first');
            return;
        }

        localStorage.setItem(STORAGE_KEY, target);
        setError(null);
        setIsLoading(true);
        api.updateDeskStatus(target, {
            onComplete: (result) => {
                setStatus(result);
                setIsLoading(false);
                toast.success('Update Desk status updated');
            },
            onError: (message) => {
                setError(message);
                setIsLoading(false);
                toast.error(`Update Desk status failed: ${message}`);
            },
        });
    };

    const handlePlan = () => {
        const target = stagingPath.trim();
        const mods = modsPath.trim();
        if (!target) {
            toast.error('Choose a staging folder first');
            return;
        }
        if (!mods) {
            toast.error('Choose a Mods folder first');
            return;
        }

        localStorage.setItem(STORAGE_KEY, target);
        localStorage.setItem(MODS_STORAGE_KEY, mods);
        setPlanError(null);
        setIsPlanning(true);
        api.updateDeskPlan(target, mods, {
            onComplete: (result) => {
                setPlan(result);
                setIsPlanning(false);
                toast.success('Update Desk plan ready');
            },
            onError: (message) => {
                setPlanError(message);
                setIsPlanning(false);
                toast.error(`Update Desk plan failed: ${message}`);
            },
        });
    };

    const handlePathSelect = (path) => {
        if (pickerTarget === 'mods') {
            setModsPath(path);
        } else {
            setStagingPath(path);
        }
    };

    return (
        <div className="min-w-0 space-y-6 p-4 md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3">
                        <div className="rounded-xl bg-sky-500/15 p-3 text-sky-200">
                            <Download size={26} />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-white">Update Desk</h1>
                            <p className="text-gray-400">Staged downloads and source bindings</p>
                        </div>
                    </div>
                </div>
            </div>

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] xl:items-end">
                    <PathField
                        label="Staging Folder"
                        value={stagingPath}
                        onChange={setStagingPath}
                        onBrowse={() => setPickerTarget('staging')}
                        placeholder={DEFAULT_STAGING_PATH}
                        browseTitle="Choose staging folder"
                    />
                    <PathField
                        label="Mods Folder"
                        value={modsPath}
                        onChange={setModsPath}
                        onBrowse={() => setPickerTarget('mods')}
                        placeholder={DEFAULT_MODS_PATH}
                        browseTitle="Choose Mods folder"
                    />
                    <button
                        onClick={handleStatus}
                        disabled={isLoading}
                        className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isLoading ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        Status
                    </button>
                    <button
                        onClick={handlePlan}
                        disabled={isPlanning}
                        className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
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
            {planError && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-200">
                    {planError}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatTile icon={ShieldCheck} label="Boundary" value={summary.readOnlyLabel} tone={summary.readOnlyLabel === 'Read-only' ? 'green' : 'red'} />
                <StatTile icon={Package} label="Items" value={summary.itemCount} tone={summary.tone} />
                <StatTile icon={FileArchive} label="Archives" value={summary.archiveCount} tone="blue" />
                <StatTile icon={AlertTriangle} label="Signals" value={issueCount} tone={issueCount ? 'amber' : 'green'} />
            </div>

            {plan && (
                <section className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                        <StatTile icon={ClipboardList} label="Plan" value={planSummary.statusLabel} tone={planSummary.tone} />
                        <StatTile icon={Package} label="Copies" value={planSummary.copyCount} tone={planSummary.copyCount ? 'green' : 'blue'} />
                        <StatTile icon={FileArchive} label="Archive Reviews" value={planSummary.archiveReviewCount} tone={planSummary.archiveReviewCount ? 'amber' : 'blue'} />
                        <StatTile icon={AlertTriangle} label="Blocked" value={planSummary.blockedCount} tone={planSummary.blockedCount ? 'red' : 'green'} />
                        <StatTile icon={ShieldCheck} label="Mods" value={planSummary.modsMutationLabel} tone={planSummary.modsMutationLabel === 'No Mods mutation' ? 'green' : 'red'} />
                    </div>

                    <section className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
                        <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                            <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                                    <ClipboardList size={20} className="text-emerald-300" />
                                    Install Plan
                                </h2>
                                <span className="w-fit rounded-md border border-gray-700 bg-black/20 px-2 py-1 text-xs uppercase text-gray-300">
                                    {planSummary.readOnlyLabel}
                                </span>
                            </div>
                            <PlanActions rows={planRows} />
                        </div>

                        <div className="space-y-4">
                            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
                                    <ShieldCheck size={20} className="text-emerald-300" />
                                    Review Gate
                                </h2>
                                <div className="space-y-3">
                                    {planSummary.planId && (
                                        <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-400">
                                            {planSummary.planId}
                                        </p>
                                    )}
                                    <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-white">
                                        {planSummary.stagingPath || stagingPath || DEFAULT_STAGING_PATH}
                                    </p>
                                    <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-white">
                                        {planSummary.modsPath || modsPath || DEFAULT_MODS_PATH}
                                    </p>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        <div className="rounded bg-black/30 px-3 py-2">
                                            <p className="text-xs uppercase tracking-wider text-gray-500">Snapshot</p>
                                            <p className="mt-1 text-gray-200">{planSummary.requiresSnapshotLabel}</p>
                                        </div>
                                        <div className="rounded bg-black/30 px-3 py-2">
                                            <p className="text-xs uppercase tracking-wider text-gray-500">Actions</p>
                                            <p className="mt-1 font-mono text-gray-200">{planSummary.actionCount}</p>
                                        </div>
                                    </div>
                                </div>
                            </section>
                            <MessageList
                                icon={CheckCircle2}
                                title="Plan Recommendations"
                                messages={plan?.recommendations || []}
                                tone="blue"
                            />
                            <MessageList
                                icon={Archive}
                                title="Plan Warnings"
                                messages={plan?.warnings || []}
                                tone="red"
                            />
                        </div>
                    </section>
                </section>
            )}

            <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h2 className="text-lg font-semibold text-white">Staged Items</h2>
                        <span className="w-fit rounded-md border border-gray-700 bg-black/20 px-2 py-1 text-xs uppercase text-gray-300">
                            {summary.statusLabel}
                        </span>
                    </div>
                    <StagedItems rows={itemRows} />
                </div>

                <div className="space-y-4">
                    <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-3 text-lg font-semibold text-white">Staging</h2>
                        <div className="space-y-3">
                            <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                                {summary.stagingPath || stagingPath || DEFAULT_STAGING_PATH}
                            </p>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <div className="rounded bg-black/30 px-3 py-2">
                                    <p className="text-xs uppercase tracking-wider text-gray-500">Packages</p>
                                    <p className="mt-1 font-mono text-gray-200">{summary.packageCount}</p>
                                </div>
                                <div className="rounded bg-black/30 px-3 py-2">
                                    <p className="text-xs uppercase tracking-wider text-gray-500">Scripts</p>
                                    <p className="mt-1 font-mono text-gray-200">{summary.scriptCount}</p>
                                </div>
                                <div className="rounded bg-black/30 px-3 py-2">
                                    <p className="text-xs uppercase tracking-wider text-gray-500">Source-bound</p>
                                    <p className="mt-1 font-mono text-gray-200">{summary.sourceBoundCount}</p>
                                </div>
                                <div className="rounded bg-black/30 px-3 py-2">
                                    <p className="text-xs uppercase tracking-wider text-gray-500">Size</p>
                                    <p className="mt-1 font-mono text-gray-200">{summary.totalSizeLabel}</p>
                                </div>
                            </div>
                        </div>
                    </section>
                    <SignalRows rows={signalRows} />
                    <MessageList
                        icon={CheckCircle2}
                        title="Recommendations"
                        messages={status?.recommendations || []}
                        tone="blue"
                    />
                    <MessageList
                        icon={Archive}
                        title="Warnings"
                        messages={status?.warnings || []}
                        tone="red"
                    />
                </div>
            </section>

            <FilePicker
                isOpen={Boolean(pickerTarget)}
                onClose={() => setPickerTarget(null)}
                onSelect={handlePathSelect}
                initialPath={pickerTarget === 'mods'
                    ? (modsPath || DEFAULT_MODS_PATH)
                    : (stagingPath || DEFAULT_STAGING_PATH)}
            />
        </div>
    );
}

export default UpdateDesk;
