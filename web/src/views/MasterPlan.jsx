import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    BrainCircuit,
    ClipboardList,
    FolderOpen,
    Gauge,
    GitCompare,
    Loader2,
    RefreshCw,
    Save,
    Search,
    ShieldCheck,
    UserSearch,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import {
    baselineChangeCount,
    summarizeBaselineStatus,
    summarizeMasterPlan,
    summarizeUpdateRegistryStatus,
    topCreatorProfiles,
    updateRegistryActionCount,
    updateRegistryAttentionEntries,
} from './masterPlanModel';
import { formatBytes } from './worldModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

function StatTile({ label, value, tone = 'gray' }) {
    const tones = {
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
        cyan: 'border-cyan-500/30 bg-cyan-950/20 text-cyan-200',
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-200',
        red: 'border-red-500/30 bg-red-950/20 text-red-200',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
        </div>
    );
}

function SectionHeader({ icon: Icon, title, count }) {
    return (
        <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
                <Icon size={18} className="text-cyan-200" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-white">{title}</h2>
            </div>
            {count != null && <span className="text-sm text-gray-500">{count}</span>}
        </div>
    );
}

function EmptyLane({ children }) {
    return <p className="rounded-lg border border-gray-800 bg-gray-950/40 p-4 text-sm text-gray-500">{children}</p>;
}

function MasterPlan() {
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [showPicker, setShowPicker] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [baselineError, setBaselineError] = useState(null);
    const [baselineStatus, setBaselineStatus] = useState(null);
    const [baselineDiff, setBaselineDiff] = useState(null);
    const [updateRegistryError, setUpdateRegistryError] = useState(null);
    const [updateRegistryStatus, setUpdateRegistryStatus] = useState(null);
    const [isScanning, setIsScanning] = useState(false);
    const [isSavingBaseline, setIsSavingBaseline] = useState(false);
    const [isDiffingBaseline, setIsDiffingBaseline] = useState(false);
    const [isRefreshingBaseline, setIsRefreshingBaseline] = useState(false);
    const [isSavingUpdateTemplate, setIsSavingUpdateTemplate] = useState(false);
    const [isRefreshingUpdateRegistry, setIsRefreshingUpdateRegistry] = useState(false);

    const summary = useMemo(() => summarizeMasterPlan(result), [result]);
    const baselineSummary = useMemo(
        () => summarizeBaselineStatus(baselineDiff || baselineStatus),
        [baselineDiff, baselineStatus],
    );
    const baselineChanges = useMemo(
        () => baselineChangeCount(baselineDiff || baselineStatus),
        [baselineDiff, baselineStatus],
    );
    const updateRegistrySummary = useMemo(
        () => summarizeUpdateRegistryStatus(updateRegistryStatus),
        [updateRegistryStatus],
    );
    const updateRegistryActions = useMemo(
        () => updateRegistryActionCount(updateRegistryStatus),
        [updateRegistryStatus],
    );
    const updateRegistryRows = useMemo(
        () => updateRegistryAttentionEntries(updateRegistryStatus, 8),
        [updateRegistryStatus],
    );
    const creators = useMemo(() => topCreatorProfiles(result, 10), [result]);
    const updateCandidates = result?.updates?.candidates || [];
    const performanceActions = result?.performance?.actions || [];
    const heavyUnits = result?.performance?.heavy_units || [];
    const catalogEntries = result?.catalog?.entries || [];

    const handlePlan = () => {
        setError(null);
        setIsScanning(true);
        api.planMaster(simsPath, {
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

    const handleSaveBaseline = () => {
        setBaselineError(null);
        setIsSavingBaseline(true);
        api.saveMasterBaseline(simsPath, 'manual', {
            onComplete: (data) => {
                setBaselineStatus({
                    baseline_exists: true,
                    baseline_path: data.latest_baseline_path,
                    summary: {
                        added: 0,
                        removed: 0,
                        changed: 0,
                        unchanged: data.summary?.catalog_entries || 0,
                        warnings: data.summary?.warnings || 0,
                    },
                });
                setBaselineDiff(null);
                setIsSavingBaseline(false);
            },
            onError: (message) => {
                setBaselineError(message);
                setIsSavingBaseline(false);
            },
            onDone: () => setIsSavingBaseline(false),
        });
    };

    const handleCompareBaseline = () => {
        setBaselineError(null);
        setIsDiffingBaseline(true);
        api.diffMasterBaseline(simsPath, null, {
            onComplete: (data) => {
                setBaselineDiff(data);
                setBaselineStatus({
                    baseline_exists: true,
                    baseline_path: data.baseline_path,
                    summary: data.summary,
                });
                setIsDiffingBaseline(false);
            },
            onError: (message) => {
                setBaselineError(message);
                setIsDiffingBaseline(false);
            },
            onDone: () => setIsDiffingBaseline(false),
        });
    };

    const handleRefreshBaseline = () => {
        setBaselineError(null);
        setIsRefreshingBaseline(true);
        api.masterBaselineStatus(simsPath, {
            onComplete: (data) => {
                setBaselineStatus(data);
                setBaselineDiff(null);
                setIsRefreshingBaseline(false);
            },
            onError: (message) => {
                setBaselineError(message);
                setIsRefreshingBaseline(false);
            },
            onDone: () => setIsRefreshingBaseline(false),
        });
    };

    const handleSaveUpdateTemplate = () => {
        setUpdateRegistryError(null);
        setIsSavingUpdateTemplate(true);
        api.saveMasterUpdateTemplate(simsPath, {
            onComplete: (data) => {
                setUpdateRegistryStatus({
                    ...data,
                    registry_exists: true,
                });
                setIsSavingUpdateTemplate(false);
            },
            onError: (message) => {
                setUpdateRegistryError(message);
                setIsSavingUpdateTemplate(false);
            },
            onDone: () => setIsSavingUpdateTemplate(false),
        });
    };

    const handleRefreshUpdateRegistry = () => {
        setUpdateRegistryError(null);
        setIsRefreshingUpdateRegistry(true);
        api.masterUpdateStatus(simsPath, {
            onComplete: (data) => {
                setUpdateRegistryStatus(data);
                setIsRefreshingUpdateRegistry(false);
            },
            onError: (message) => {
                setUpdateRegistryError(message);
                setIsRefreshingUpdateRegistry(false);
            },
            onDone: () => setIsRefreshingUpdateRegistry(false),
        });
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div className="flex items-center gap-3">
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/30 p-3 text-cyan-200">
                        <BrainCircuit size={26} />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white">Master Plan</h1>
                        <p className="mt-1 text-sm text-gray-400">Update catalog, performance pressure, and creator control</p>
                    </div>
                </div>
                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                    <div className="min-w-0 md:w-[34rem]">
                        <label htmlFor="master-sims-path" className="mb-2 block text-sm font-medium text-gray-300">
                            Sims 4 folder
                        </label>
                        <div className="flex rounded-lg border border-gray-700 bg-gray-950/60">
                            <input
                                id="master-sims-path"
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
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 font-medium text-gray-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isScanning ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
                        Build Plan
                    </button>
                </div>
            </div>

            <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4 text-cyan-100">
                <div className="flex items-start gap-3">
                    <ShieldCheck size={20} className="mt-0.5 shrink-0" />
                    <p className="text-sm leading-6">
                        This lane is local and read-only. It classifies update tracking gaps, creator ownership, and load-pressure hotspots from the current inventory.
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

            <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <GitCompare size={18} className="text-cyan-200" />
                            <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
                                Catalog Baseline
                            </h2>
                        </div>
                        <div className="mt-4 grid gap-3 md:grid-cols-4">
                            <StatTile label="Added" value={baselineSummary.added} tone={baselineSummary.added ? 'amber' : 'emerald'} />
                            <StatTile label="Changed" value={baselineSummary.changed} tone={baselineSummary.changed ? 'amber' : 'emerald'} />
                            <StatTile label="Removed" value={baselineSummary.removed} tone={baselineSummary.removed ? 'red' : 'emerald'} />
                            <StatTile label="Unchanged" value={baselineSummary.unchanged} />
                        </div>
                        {baselineSummary.baselinePath ? (
                            <p className="mt-3 break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-500">
                                {baselineSummary.baselinePath}
                            </p>
                        ) : (
                            <p className="mt-3 text-sm text-gray-500">No baseline manifest selected.</p>
                        )}
                        {baselineChanges > 0 && (
                            <p className="mt-3 text-sm text-amber-200">
                                {baselineChanges} catalog change(s) since the selected baseline.
                            </p>
                        )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={handleSaveBaseline}
                            disabled={isSavingBaseline || !simsPath.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-medium text-gray-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isSavingBaseline ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                            Save Baseline
                        </button>
                        <button
                            type="button"
                            onClick={handleCompareBaseline}
                            disabled={isDiffingBaseline || !simsPath.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-cyan-400/40 px-3 py-2 text-sm font-medium text-cyan-50 transition hover:bg-cyan-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isDiffingBaseline ? <Loader2 size={16} className="animate-spin" /> : <GitCompare size={16} />}
                            Compare
                        </button>
                        <button
                            type="button"
                            onClick={handleRefreshBaseline}
                            disabled={isRefreshingBaseline || !simsPath.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm font-medium text-gray-200 transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isRefreshingBaseline ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                            Refresh
                        </button>
                    </div>
                </div>
                <AnimatePresence>
                    {baselineError && (
                        <motion.div
                            initial={{ opacity: 0, y: -6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="mt-4 rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-sm text-red-200"
                        >
                            {baselineError}
                        </motion.div>
                    )}
                </AnimatePresence>
                {baselineDiff && (
                    <div className="mt-4 grid gap-3 xl:grid-cols-3">
                        {baselineDiff.added?.slice(0, 6).map((entry) => (
                            <div key={`added-${entry.unit_id}`} className="rounded-lg border border-amber-500/25 bg-amber-950/10 p-3">
                                <p className="text-xs uppercase text-amber-200">Added</p>
                                <p className="mt-2 break-words text-sm font-medium text-white">{entry.unit_name}</p>
                            </div>
                        ))}
                        {baselineDiff.changed?.slice(0, 6).map((entry) => (
                            <div key={`changed-${entry.current.unit_id}`} className="rounded-lg border border-cyan-500/25 bg-cyan-950/10 p-3">
                                <p className="text-xs uppercase text-cyan-200">Changed</p>
                                <p className="mt-2 break-words text-sm font-medium text-white">{entry.current.unit_name}</p>
                            </div>
                        ))}
                        {baselineDiff.removed?.slice(0, 6).map((entry) => (
                            <div key={`removed-${entry.unit_id}`} className="rounded-lg border border-red-500/25 bg-red-950/10 p-3">
                                <p className="text-xs uppercase text-red-200">Removed</p>
                                <p className="mt-2 break-words text-sm font-medium text-white">{entry.unit_name}</p>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <ClipboardList size={18} className="text-cyan-200" />
                            <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
                                Local Update Registry
                            </h2>
                        </div>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-gray-400">
                            This registry is a local template for source links and latest-version notes. It does not check the internet or modify installed mods.
                        </p>
                        <div className="mt-4 grid gap-3 md:grid-cols-4">
                            <StatTile label="Tracked Sources" value={updateRegistrySummary.trackedSources} tone="cyan" />
                            <StatTile label="Missing Sources" value={updateRegistrySummary.missingSources} tone={updateRegistrySummary.missingSources ? 'amber' : 'emerald'} />
                            <StatTile label="Outdated" value={updateRegistrySummary.outdated} tone={updateRegistrySummary.outdated ? 'red' : 'emerald'} />
                            <StatTile label="Needs Check" value={updateRegistrySummary.needsCheck + updateRegistrySummary.noInstalledVersion} tone={updateRegistrySummary.needsCheck || updateRegistrySummary.noInstalledVersion ? 'amber' : 'emerald'} />
                        </div>
                        {updateRegistrySummary.registryPath ? (
                            <p className="mt-3 break-all rounded bg-black/30 px-3 py-2 font-mono text-xs text-gray-500">
                                {updateRegistrySummary.registryPath}
                            </p>
                        ) : (
                            <p className="mt-3 text-sm text-gray-500">No update registry template found.</p>
                        )}
                        {updateRegistryActions > 0 && (
                            <p className="mt-3 text-sm text-amber-200">
                                {updateRegistryActions} update tracking item(s) need source, version, or review data.
                            </p>
                        )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={handleSaveUpdateTemplate}
                            disabled={isSavingUpdateTemplate || !simsPath.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-medium text-gray-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isSavingUpdateTemplate ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                            Save Template
                        </button>
                        <button
                            type="button"
                            onClick={handleRefreshUpdateRegistry}
                            disabled={isRefreshingUpdateRegistry || !simsPath.trim()}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm font-medium text-gray-200 transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isRefreshingUpdateRegistry ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                            Refresh Status
                        </button>
                    </div>
                </div>
                <AnimatePresence>
                    {updateRegistryError && (
                        <motion.div
                            initial={{ opacity: 0, y: -6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="mt-4 rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-sm text-red-200"
                        >
                            {updateRegistryError}
                        </motion.div>
                    )}
                </AnimatePresence>
                {updateRegistryRows.length > 0 && (
                    <div className="mt-4 grid gap-3 xl:grid-cols-4">
                        {updateRegistryRows.map((entry) => (
                            <div key={`${entry.status}-${entry.relative_path}`} className="rounded-lg border border-amber-500/25 bg-amber-950/10 p-3">
                                <p className="text-xs uppercase text-amber-200">
                                    {entry.status.replaceAll('_', ' ')}
                                </p>
                                <p className="mt-2 break-words text-sm font-medium text-white">{entry.unit_name}</p>
                                <p className="mt-2 text-xs text-gray-500">
                                    Installed {entry.installed_version || 'unknown'} - Latest {entry.latest_version || 'not recorded'}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {result && (
                <>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                        <StatTile label="Active Units" value={summary.activeUnits} tone="cyan" />
                        <StatTile label="Catalog" value={summary.catalogEntries} tone="emerald" />
                        <StatTile label="Creators" value={summary.creatorProfiles} />
                        <StatTile label="Updates" value={summary.updateCandidates} tone={summary.updateCandidates ? 'amber' : 'emerald'} />
                        <StatTile label="Performance" value={summary.performanceActions} tone={summary.performanceActions ? 'red' : 'emerald'} />
                        <StatTile label="Warnings" value={summary.warnings} />
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                            <SectionHeader icon={Search} title="Update Candidates" count={updateCandidates.length} />
                            {updateCandidates.length === 0 ? (
                                <EmptyLane>No script-mod update tracking gaps found.</EmptyLane>
                            ) : (
                                <div className="space-y-3">
                                    {updateCandidates.slice(0, 20).map((candidate) => (
                                        <div key={candidate.unit_id} className="rounded-lg border border-amber-500/25 bg-amber-950/10 p-4">
                                            <p className="font-medium text-white">{candidate.unit_name}</p>
                                            <p className="mt-2 text-sm text-amber-100/80">{candidate.suggested_action}</p>
                                            <span className="mt-3 inline-flex rounded-md bg-amber-500/15 px-2 py-1 text-xs uppercase text-amber-200">
                                                {candidate.reason.replaceAll('_', ' ')}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                            <SectionHeader icon={Gauge} title="Performance Pressure" count={performanceActions.length} />
                            {performanceActions.length === 0 ? (
                                <EmptyLane>No load-pressure action crossed the current threshold.</EmptyLane>
                            ) : (
                                <div className="space-y-3">
                                    {performanceActions.map((action) => (
                                        <div key={action.kind} className="rounded-lg border border-red-500/25 bg-red-950/10 p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <p className="font-medium text-white">{action.title}</p>
                                                <span className="rounded-md bg-red-500/15 px-2 py-1 text-xs uppercase text-red-200">
                                                    {action.severity}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm text-gray-400">{action.count} item(s)</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                            <SectionHeader icon={Gauge} title="Heavy Active Units" count={heavyUnits.length} />
                            {heavyUnits.length === 0 ? (
                                <EmptyLane>No heavy active unit crossed the current threshold.</EmptyLane>
                            ) : (
                                <div className="space-y-3">
                                    {heavyUnits.slice(0, 12).map((unit) => (
                                        <div key={unit.unit_id} className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
                                            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                                                <p className="break-words font-medium text-white">{unit.unit_name}</p>
                                                <span className="w-fit rounded-md bg-gray-800 px-2 py-1 text-xs text-gray-300">
                                                    {formatBytes(unit.total_size_bytes)}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-xs text-gray-500">
                                                {unit.package_count} package(s), {unit.script_count} script(s)
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                            <SectionHeader icon={UserSearch} title="Creator Profiles" count={creators.length} />
                            {creators.length === 0 ? (
                                <EmptyLane>No creator profiles found.</EmptyLane>
                            ) : (
                                <div className="space-y-3">
                                    {creators.map((profile) => (
                                        <div key={profile.creator} className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
                                            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                                                <p className="font-medium text-white">{profile.creator}</p>
                                                <span className="w-fit rounded-md bg-gray-800 px-2 py-1 text-xs text-gray-300">
                                                    {profile.unit_count} unit(s)
                                                </span>
                                            </div>
                                            <p className="mt-2 text-xs text-gray-500">
                                                {profile.package_count} package(s), {profile.script_count} script(s), {formatBytes(profile.total_size_bytes)}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>
                    </div>

                    <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
                        <SectionHeader icon={BrainCircuit} title="Catalog Preview" count={catalogEntries.length} />
                        {catalogEntries.length === 0 ? (
                            <EmptyLane>No catalog entries found.</EmptyLane>
                        ) : (
                            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                                {catalogEntries.slice(0, 18).map((entry) => (
                                    <div key={entry.unit_id} className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
                                        <p className="break-words font-medium text-white">{entry.unit_name}</p>
                                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                                            <span className="rounded-md bg-gray-800 px-2 py-1 text-gray-300">{entry.creator}</span>
                                            <span className="rounded-md bg-gray-800 px-2 py-1 text-gray-300">
                                                {entry.version_signal || 'no version'}
                                            </span>
                                            <span className="rounded-md bg-gray-800 px-2 py-1 text-gray-300">
                                                {entry.update_status.replaceAll('_', ' ')}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>
                </>
            )}

            {!result && !isScanning && (
                <div className="rounded-xl border border-gray-800 bg-gray-900/35 p-8 text-center text-gray-500">
                    <BrainCircuit size={34} className="mx-auto mb-3 text-gray-600" />
                    <p>No master plan loaded.</p>
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

export default MasterPlan;
