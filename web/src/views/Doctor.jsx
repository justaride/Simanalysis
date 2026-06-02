import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
    AlertTriangle,
    CheckCircle,
    Download,
    FileWarning,
    FolderOpen,
    Loader2,
    Microscope,
    Search,
    ShieldCheck,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

function countIssues(entries) {
    return entries.reduce((total, group) => total + group.items.length, 0);
}

function formatKey(key) {
    if (!key) return 'no key';
    if (typeof key === 'object') return key.hex || key.decimal || 'unknown key';
    return String(key);
}

function uniquePackages(hits = []) {
    return [...new Set(hits.map((hit) => hit.package_name).filter(Boolean))];
}

function uniquePackagePaths(hits = []) {
    return [...new Set(hits.map((hit) => hit.package_path).filter(Boolean))];
}

function collectScriptEvidence(result) {
    const byMod = {};
    const findings = result?.script_crashes?.findings || [];
    findings.forEach((finding) => {
        (finding.suspects || []).forEach((suspect) => {
            if (!suspect.mod) return;
            if (!byMod[suspect.mod]) byMod[suspect.mod] = new Set();
            (suspect.evidence || []).forEach((path) => byMod[suspect.mod].add(path));
        });
    });
    return Object.fromEntries(Object.entries(byMod).map(([mod, paths]) => [mod, [...paths]]));
}

function buildGroups(result) {
    const rankedMods = result?.script_crashes?.ranked_mods || [];
    const uiFindings = result?.ui_crashes?.findings || [];
    const scriptEvidence = collectScriptEvidence(result);
    const scriptItems = rankedMods.map((item) => ({
        ...item,
        evidence: scriptEvidence[item.mod] || [],
    }));
    const errorItems = [
        ...(result?.script_crashes?.parse_errors || []).map((message) => ({
            source: 'Script log parser',
            message,
        })),
        ...(result?.ui_crashes?.parse_errors || []).map((message) => ({
            source: 'UI log parser',
            message,
        })),
        ...(result?.ui_crashes?.index_errors || []).map((message) => ({
            source: 'Package index',
            message,
        })),
    ];

    return {
        needsAttention: [
            {
                label: 'Script suspects still active',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'active'),
            },
            {
                label: 'UI resources found in active packages',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'active'),
            },
        ],
        alreadyDisabled: [
            {
                label: 'Script suspects already disabled',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'disabled'),
            },
            {
                label: 'UI resources already disabled',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'disabled'),
            },
        ],
        missingUnknown: [
            {
                label: 'Script references not installed',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'not_installed'),
            },
            {
                label: 'UI resources missing or without keys',
                kind: 'ui',
                items: uiFindings.filter((item) => ['not_found', 'no_key'].includes(item.status)),
            },
        ],
        errors: [
            {
                label: 'Parse and index errors',
                kind: 'error',
                items: errorItems,
            },
        ],
    };
}

function StatTile({ label, value, tone = 'blue' }) {
    const tones = {
        blue: 'text-blue-300 bg-blue-500/10 border-blue-500/30',
        amber: 'text-amber-300 bg-amber-500/10 border-amber-500/30',
        green: 'text-green-300 bg-green-500/10 border-green-500/30',
        red: 'text-red-300 bg-red-500/10 border-red-500/30',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-2 text-3xl font-bold text-white">{value}</p>
        </div>
    );
}

function ScriptFinding({ item }) {
    const evidence = item.evidence || [];
    return (
        <div className="rounded-lg border border-gray-700/70 bg-gray-900/50 p-4">
            <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                        <p className="truncate font-semibold text-white" title={item.mod}>
                            {item.mod}
                        </p>
                        <p className="mt-1 text-sm text-gray-400">
                            Top suspect in {item.top_suspect_count || 0} crash(es)
                            {item.status !== 'not_installed' ? `, seen in ${item.crash_count || 0}` : ''}
                        </p>
                    </div>
                    <span className="w-fit rounded-md border border-gray-600 px-2 py-1 text-xs uppercase text-gray-300">
                        {item.status || 'unknown'}
                    </span>
                </div>
                {evidence.length > 0 && (
                    <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Evidence</p>
                        <div className="space-y-1">
                            {evidence.slice(0, 3).map((path) => (
                                <p key={path} className="truncate rounded bg-black/30 px-2 py-1 font-mono text-xs text-gray-400" title={path}>
                                    {path}
                                </p>
                            ))}
                            {evidence.length > 3 && (
                                <p className="text-xs text-gray-500">+{evidence.length - 3} more evidence path(s)</p>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function UIFinding({ item }) {
    const packages = uniquePackages(item.hits);
    const packagePaths = uniquePackagePaths(item.hits);
    return (
        <div className="rounded-lg border border-gray-700/70 bg-gray-900/50 p-4">
            <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                        <p className="line-clamp-2 font-semibold text-white" title={item.report?.message}>
                            {item.report?.message || item.reason || 'UI exception'}
                        </p>
                        <p className="mt-1 text-sm text-gray-400">
                            {item.report?.occurrences || 1} occurrence(s)
                            {item.report?.category_id ? ` · ${item.report.category_id}` : ''}
                        </p>
                    </div>
                    <span className="w-fit rounded-md border border-gray-600 px-2 py-1 text-xs uppercase text-gray-300">
                        {item.status}
                    </span>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                    {(item.keys || []).map((key) => (
                        <span key={formatKey(key)} className="rounded bg-gray-800 px-2 py-1 font-mono text-gray-300">
                            {formatKey(key)}
                        </span>
                    ))}
                    {packages.map((pkg) => (
                        <span key={pkg} className="rounded bg-blue-950/60 px-2 py-1 text-blue-200">
                            {pkg}
                        </span>
                    ))}
                </div>
                {packagePaths.length > 0 && (
                    <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Package paths</p>
                        <div className="space-y-1">
                            {packagePaths.slice(0, 3).map((path) => (
                                <p key={path} className="truncate rounded bg-black/30 px-2 py-1 font-mono text-xs text-gray-400" title={path}>
                                    {path}
                                </p>
                            ))}
                            {packagePaths.length > 3 && (
                                <p className="text-xs text-gray-500">+{packagePaths.length - 3} more package path(s)</p>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function ErrorFinding({ item }) {
    return (
        <div className="rounded-lg border border-gray-700/70 bg-gray-900/50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-300">{item.source}</p>
            <p className="mt-2 break-words font-mono text-xs text-gray-300">{item.message}</p>
        </div>
    );
}

function FindingGroup({ title, description, icon: Icon, tone, groups }) {
    const total = countIssues(groups);
    const border = {
        red: 'border-red-500/40 bg-red-950/10',
        green: 'border-green-500/40 bg-green-950/10',
        amber: 'border-amber-500/40 bg-amber-950/10',
    }[tone];
    const iconTone = {
        red: 'text-red-300 bg-red-500/15',
        green: 'text-green-300 bg-green-500/15',
        amber: 'text-amber-300 bg-amber-500/15',
    }[tone];

    return (
        <section className={`rounded-xl border ${border}`}>
            <div className="flex items-start justify-between gap-4 border-b border-gray-700/50 p-5">
                <div className="flex items-start gap-3">
                    <div className={`rounded-lg p-2 ${iconTone}`}>
                        <Icon size={20} />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-white">{title}</h2>
                        <p className="mt-1 text-sm text-gray-400">{description}</p>
                    </div>
                </div>
                <span className="rounded-lg bg-gray-900/80 px-3 py-1 text-sm font-semibold text-white">{total}</span>
            </div>

            <div className="space-y-4 p-5">
                {total === 0 ? (
                    <p className="rounded-lg border border-gray-800 bg-gray-900/40 p-4 text-sm text-gray-500">
                        Nothing in this group.
                    </p>
                ) : (
                    groups.map((group) =>
                        group.items.length > 0 ? (
                            <div key={group.label}>
                                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                                    {group.label}
                                </p>
                                <div className="space-y-3">
                                    {group.items.map((item, index) =>
                                        group.kind === 'error' ? (
                                            <ErrorFinding key={`${group.label}-${index}`} item={item} />
                                        ) : group.kind === 'script' ? (
                                            <ScriptFinding key={`${group.label}-${item.mod}-${index}`} item={item} />
                                        ) : (
                                            <UIFinding
                                                key={`${group.label}-${item.report?.signature || index}`}
                                                item={item}
                                            />
                                        )
                                    )}
                                </div>
                            </div>
                        ) : null
                    )
                )}
            </div>
        </section>
    );
}

function Doctor() {
    const location = useLocation();
    const navigate = useNavigate();
    const [simsPath, setSimsPath] = useState(location.state?.simsPath || DEFAULT_SIMS_PATH);
    const [modsPath, setModsPath] = useState(location.state?.modsPath || '');
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showModsPicker, setShowModsPicker] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [progress, setProgress] = useState(null);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const groups = useMemo(() => buildGroups(result), [result]);
    const summary = result?.summary || {};
    const activeTotal = (summary.script_active || 0) + (summary.ui_active || 0);
    const disabledTotal = (summary.script_disabled || 0) + (summary.ui_disabled || 0);
    const unknownTotal =
        (summary.script_not_installed || 0) + (summary.ui_not_found || 0) + (summary.ui_no_key || 0);

    const handleScan = () => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            return;
        }
        setIsScanning(true);
        setError(null);
        setProgress(null);
        setResult(null);

        api.scanDoctor(simsPath.trim(), modsPath.trim() || null, {
            onProgress: (nextProgress) => setProgress(nextProgress),
            onComplete: (data) => {
                setResult(data);
                setIsScanning(false);
                setProgress(null);
            },
            onError: (message) => {
                setError(message);
                setIsScanning(false);
                setProgress(null);
            },
        });
    };

    const handleExport = () => {
        if (!result) return;
        const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `simanalysis-doctor-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-7xl space-y-6">
                <motion.header
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
                >
                    <div>
                        <h1 className="flex items-center gap-3 text-3xl font-bold text-white">
                            <span className="rounded-xl bg-blue-500/15 p-2 text-blue-300">
                                <Microscope size={28} />
                            </span>
                            Doctor
                        </h1>
                        <p className="mt-2 max-w-3xl text-gray-400">
                            One read-only pass over script crash logs and UI freeze logs.
                        </p>
                    </div>
                    {result && (
                        <div className="flex flex-wrap gap-2">
                            {activeTotal > 0 && (
                                <button
                                    onClick={() => navigate('/treatment', { state: { simsPath, modsPath } })}
                                    className="flex w-fit items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
                                >
                                    <ShieldCheck size={17} />
                                    Open Treatment
                                </button>
                            )}
                            <button
                                onClick={handleExport}
                                className="flex w-fit items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
                            >
                                <Download size={17} />
                                Export JSON
                            </button>
                        </div>
                    )}
                </motion.header>

                <section className="glass-card p-5">
                    <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
                        <div>
                            <label className="mb-2 block text-sm font-medium text-gray-300">Sims 4 Folder</label>
                            <div className="flex gap-2">
                                <input
                                    value={simsPath}
                                    onChange={(event) => setSimsPath(event.target.value)}
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    className="rounded-lg border border-gray-700 bg-gray-800 px-3 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label className="mb-2 block text-sm font-medium text-gray-300">Mods Folder</label>
                            <div className="flex gap-2">
                                <input
                                    value={modsPath}
                                    onChange={(event) => setModsPath(event.target.value)}
                                    placeholder="Default: Sims 4 folder / Mods"
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
                                />
                                <button
                                    onClick={() => setShowModsPicker(true)}
                                    className="rounded-lg border border-gray-700 bg-gray-800 px-3 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Mods folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={handleScan}
                                disabled={isScanning}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60 lg:w-auto"
                            >
                                {isScanning ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
                                {isScanning ? 'Scanning' : 'Run Doctor'}
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {progress && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-blue-500/30 bg-blue-950/20 p-3 text-sm text-blue-100"
                            >
                                {progress.stage || progress.file || 'Scanning'} · {progress.current || 0}/
                                {progress.total || 0}
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

                {result ? (
                    <>
                        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
                            <StatTile label="Needs Attention" value={activeTotal} tone={activeTotal ? 'red' : 'green'} />
                            <StatTile label="Already Disabled" value={disabledTotal} tone="green" />
                            <StatTile label="Missing / Unknown" value={unknownTotal} tone="amber" />
                            <StatTile
                                label="Errors"
                                value={(summary.parse_errors || 0) + (summary.index_errors || 0)}
                                tone={(summary.parse_errors || 0) + (summary.index_errors || 0) ? 'amber' : 'blue'}
                            />
                        </section>

                        <div className="grid gap-6 xl:grid-cols-4">
                            <FindingGroup
                                title="Needs Attention"
                                description="Active mods or packages still implicated by current logs."
                                icon={AlertTriangle}
                                tone="red"
                                groups={groups.needsAttention}
                            />
                            <FindingGroup
                                title="Already Disabled"
                                description="Evidence points at files that are already set aside."
                                icon={ShieldCheck}
                                tone="green"
                                groups={groups.alreadyDisabled}
                            />
                            <FindingGroup
                                title="Missing or Unknown"
                                description="References that cannot be resolved to an active installed file."
                                icon={FileWarning}
                                tone="amber"
                                groups={groups.missingUnknown}
                            />
                            <FindingGroup
                                title="Errors"
                                description="Log parse and package index errors surfaced during the scan."
                                icon={FileWarning}
                                tone="amber"
                                groups={groups.errors}
                            />
                        </div>

                        <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
                                <CheckCircle className="text-blue-300" size={20} />
                                Scan Details
                            </h2>
                            <div className="grid gap-3 text-sm text-gray-400 md:grid-cols-2">
                                <p>Script reports: {summary.script_reports || 0}</p>
                                <p>UI findings: {summary.ui_findings || 0}</p>
                                <p>UI occurrences: {summary.ui_occurrences || 0}</p>
                                <p>Index errors: {summary.index_errors || 0}</p>
                            </div>
                            {((result.script_crashes?.parse_errors || []).length > 0 ||
                                (result.ui_crashes?.parse_errors || []).length > 0 ||
                                (result.ui_crashes?.index_errors || []).length > 0) && (
                                <pre className="mt-4 max-h-56 overflow-auto rounded-lg bg-black/40 p-3 text-xs text-gray-300">
                                    {[
                                        ...(result.script_crashes?.parse_errors || []),
                                        ...(result.ui_crashes?.parse_errors || []),
                                        ...(result.ui_crashes?.index_errors || []),
                                    ].join('\n')}
                                </pre>
                            )}
                        </section>
                    </>
                ) : (
                    <section className="flex min-h-[280px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-gray-900/40 text-center">
                        <Microscope className="mb-4 text-gray-600" size={52} />
                        <h2 className="text-xl font-semibold text-white">No Doctor scan yet</h2>
                        <p className="mt-2 max-w-md text-sm text-gray-500">
                            Run a scan to combine script crash and UI freeze evidence into one report.
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
                    isOpen={showModsPicker}
                    onClose={() => setShowModsPicker(false)}
                    onSelect={(path) => setModsPath(path)}
                    initialPath={modsPath || simsPath}
                    selectDirectory={true}
                />
            </div>
        </div>
    );
}

export default Doctor;
