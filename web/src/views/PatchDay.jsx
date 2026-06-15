import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    FileClock,
    FolderOpen,
    Loader2,
    RefreshCw,
    Save,
    ShieldAlert,
    ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import {
    canRecordPatchBaseline,
    summarizePatchDayStatus,
    toPatchRiskRows,
} from './patchDayModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

const toneClasses = {
    blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
    amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
    green: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
    red: 'border-red-500/30 bg-red-950/20 text-red-100',
};

function PathField({ label, value, onChange, onBrowse, placeholder }) {
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
                    title={`Choose ${label}`}
                >
                    <FolderOpen size={18} />
                </button>
            </div>
        </div>
    );
}

function StatePathField({ value, onChange }) {
    return (
        <div className="min-w-0">
            <label className="mb-2 block text-sm font-medium text-gray-300">State JSON</label>
            <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder="Default: ~/.simanalysis/patch-day-state.json"
                className="w-full min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
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

function RiskList({ risks }) {
    if (risks.length === 0) {
        return (
            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5 text-sm text-gray-500">
                No post-patch risk classes are active for this status.
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {risks.map((risk) => (
                <div key={risk.id} className="rounded-xl border border-amber-500/25 bg-amber-950/10 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <p className="font-semibold text-white">{risk.label}</p>
                        <span className="w-fit rounded-md border border-amber-500/30 bg-black/20 px-2 py-1 text-xs uppercase text-amber-100">
                            {risk.statusLabel}
                        </span>
                    </div>
                    {risk.reason && <p className="mt-2 text-sm text-amber-100/75">{risk.reason}</p>}
                </div>
            ))}
        </div>
    );
}

function MessageList({ icon: Icon, title, messages, tone }) {
    if (!messages?.length) {
        return null;
    }
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

function ConfirmRecordModal({ summary, busy, onCancel, onConfirm }) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-lg rounded-xl border border-gray-700 bg-gray-950 p-5 shadow-2xl">
                <h2 className="text-xl font-semibold text-white">Record Patch Day baseline</h2>
                <div className="mt-4 space-y-3 text-sm text-gray-300">
                    <p>Current game version</p>
                    <p className="break-all rounded-lg bg-black/30 px-3 py-2 font-mono text-white">
                        {summary.currentVersion}
                    </p>
                    <p className="text-gray-500">
                        This updates Simanalysis state only. It does not move, enable, disable, or delete Sims files.
                    </p>
                </div>
                <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                    <button
                        onClick={onCancel}
                        disabled={busy}
                        className="h-10 rounded-lg border border-gray-700 px-4 text-sm text-gray-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={busy}
                        className="flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {busy ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                        Record
                    </button>
                </div>
            </div>
        </div>
    );
}

function PatchDay() {
    const [simsPath, setSimsPath] = useProfileDefaultPath('simsPath', {
        storageKey: 'patch-day-root-path',
        fallback: DEFAULT_SIMS_PATH,
    });
    const [statePath, setStatePath] = useState(() => localStorage.getItem('patch-day-state-path') || '');
    const [showFilePicker, setShowFilePicker] = useState(false);
    const [status, setStatus] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [confirmRecord, setConfirmRecord] = useState(false);
    const [error, setError] = useState(null);

    const summary = useMemo(() => summarizePatchDayStatus(status || {}), [status]);
    const riskRows = useMemo(() => toPatchRiskRows(status || {}), [status]);
    const canRecord = canRecordPatchBaseline(status || {});

    const options = () => {
        const trimmedState = statePath.trim();
        if (trimmedState) {
            localStorage.setItem('patch-day-state-path', trimmedState);
            return { state: trimmedState };
        }
        localStorage.removeItem('patch-day-state-path');
        return {};
    };

    const handleStatus = () => {
        const target = simsPath.trim();
        if (!target) {
            toast.error('Choose a Sims 4 folder first');
            return;
        }

        localStorage.setItem('patch-day-root-path', target);
        setError(null);
        setIsLoading(true);
        api.patchDayStatus(target, {
            onComplete: (result) => {
                setStatus(result);
                setIsLoading(false);
                toast.success('Patch Day status updated');
            },
            onError: (message) => {
                setError(message);
                setIsLoading(false);
                toast.error(`Patch Day status failed: ${message}`);
            },
        }, options());
    };

    const handleRecord = () => {
        const target = simsPath.trim();
        if (!target || !canRecord) {
            return;
        }

        setError(null);
        setIsRecording(true);
        api.patchDayRecord(target, {
            onComplete: (result) => {
                setStatus(result);
                setIsRecording(false);
                setConfirmRecord(false);
                toast.success('Patch Day baseline recorded');
            },
            onError: (message) => {
                setError(message);
                setIsRecording(false);
                toast.error(`Patch Day record failed: ${message}`);
            },
        }, options());
    };

    return (
        <div className="min-w-0 space-y-6 p-4 md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3">
                        <div className="rounded-xl bg-amber-500/15 p-3 text-amber-200">
                            <ShieldCheck size={26} />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-white">Patch Day</h1>
                            <p className="text-gray-400">Game version baseline and post-patch risk state</p>
                        </div>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={handleStatus}
                        disabled={isLoading || isRecording}
                        className="flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isLoading ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        Status
                    </button>
                    <button
                        onClick={() => setConfirmRecord(true)}
                        disabled={!canRecord || isLoading || isRecording}
                        className="flex h-10 items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/20 px-4 text-sm font-medium text-emerald-100 hover:bg-emerald-900/30 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <Save size={16} />
                        Record Baseline
                    </button>
                </div>
            </div>

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <PathField
                        label="Sims 4 Folder"
                        value={simsPath}
                        onChange={setSimsPath}
                        onBrowse={() => setShowFilePicker(true)}
                        placeholder={DEFAULT_SIMS_PATH}
                    />
                    <StatePathField value={statePath} onChange={setStatePath} />
                </div>
            </section>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-200">
                    {error}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatTile icon={FileClock} label="Status" value={summary.statusLabel} tone={summary.tone} />
                <StatTile icon={ShieldAlert} label="Risks" value={summary.riskCount} tone={summary.riskCount ? 'amber' : 'green'} />
                <StatTile icon={CheckCircle2} label="Current Version" value={summary.currentVersion} tone="blue" />
                <StatTile icon={AlertTriangle} label="Warnings" value={summary.warningCount} tone={summary.warningCount ? 'red' : 'green'} />
            </div>

            <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
                <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h2 className="text-lg font-semibold text-white">Risk Classes</h2>
                        <span className="w-fit rounded-md border border-gray-700 bg-black/20 px-2 py-1 text-xs uppercase text-gray-300">
                            {summary.automaticReenableLabel}
                        </span>
                    </div>
                    <RiskList risks={riskRows} />
                </div>

                <div className="space-y-4">
                    <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                        <h2 className="mb-3 text-lg font-semibold text-white">Versions</h2>
                        <div className="space-y-3">
                            <div>
                                <p className="mb-1 text-xs uppercase tracking-wider text-gray-500">Current</p>
                                <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                                    {summary.currentVersion}
                                </p>
                            </div>
                            <div>
                                <p className="mb-1 text-xs uppercase tracking-wider text-gray-500">Last Known</p>
                                <p className="break-all rounded bg-black/30 px-3 py-2 font-mono text-sm text-white">
                                    {summary.lastKnownVersion}
                                </p>
                            </div>
                        </div>
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

            {confirmRecord && (
                <ConfirmRecordModal
                    summary={summary}
                    busy={isRecording}
                    onCancel={() => setConfirmRecord(false)}
                    onConfirm={handleRecord}
                />
            )}
        </div>
    );
}

export default PatchDay;
