import { useMemo, useState } from 'react';
import {
    AlertTriangle,
    Archive,
    Database,
    FolderOpen,
    HardDrive,
    Loader2,
    Package,
    Search,
    ShieldAlert,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';
import { formatBytes, groupUnitsByStatus, summarizeWorld } from './worldModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

const GROUPS = [
    { key: 'active', title: 'Active Mods', tone: 'emerald' },
    { key: 'disabled', title: 'Disabled', tone: 'amber' },
    { key: 'quarantined', title: 'Quarantined', tone: 'red' },
    { key: 'archived', title: 'Archive', tone: 'blue' },
    { key: 'unknown', title: 'Unknown', tone: 'gray' },
];

function StatTile({ icon: Icon, label, value, tone = 'gray' }) {
    const tones = {
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-200',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-200',
        red: 'border-red-500/30 bg-red-950/20 text-red-200',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-200',
    };

    return (
        <div className={`rounded-xl border p-4 ${tones[tone]}`}>
            <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
                <Icon size={18} className="shrink-0 opacity-80" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
        </div>
    );
}

function UnitRow({ unit }) {
    return (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <p className="break-words font-medium text-white">{unit.name || 'Unnamed unit'}</p>
                    <p className="mt-1 break-all font-mono text-xs text-gray-500">{unit.relative_path || unit.path}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-md bg-gray-800 px-2 py-1 uppercase text-gray-300">
                        {unit.kind || 'unit'}
                    </span>
                    <span className="rounded-md bg-blue-500/10 px-2 py-1 text-blue-200">
                        {unit.file_count || 0} file(s)
                    </span>
                    <span className="rounded-md bg-emerald-500/10 px-2 py-1 text-emerald-200">
                        {formatBytes(unit.total_size_bytes || 0)}
                    </span>
                </div>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-gray-400 sm:grid-cols-3">
                <span>{unit.package_count || 0} package</span>
                <span>{unit.script_count || 0} script</span>
                <span className="truncate font-mono" title={unit.identity?.sha256}>
                    {unit.identity?.sha256?.slice(0, 12) || 'no identity'}
                </span>
            </div>
        </div>
    );
}

function UnitGroup({ group, units }) {
    if (!units.length) return null;

    const toneClass = {
        emerald: 'text-emerald-200 border-emerald-500/30',
        amber: 'text-amber-200 border-amber-500/30',
        red: 'text-red-200 border-red-500/30',
        blue: 'text-blue-200 border-blue-500/30',
        gray: 'text-gray-300 border-gray-700',
    }[group.tone];

    return (
        <section className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className={`rounded-md border px-2 py-1 text-sm font-semibold ${toneClass}`}>
                    {group.title}
                </h2>
                <span className="text-sm text-gray-500">{units.length}</span>
            </div>
            <div className="space-y-3">
                {units.slice(0, 30).map((unit) => (
                    <UnitRow key={unit.unit_id || unit.path} unit={unit} />
                ))}
            </div>
            {units.length > 30 && (
                <p className="mt-3 text-sm text-gray-500">+{units.length - 30} more unit(s)</p>
            )}
        </section>
    );
}

function EvidenceList({ title, entries = [] }) {
    if (!entries.length) return null;
    return (
        <div className="rounded-xl border border-gray-800 bg-gray-900/35 p-4">
            <h2 className="mb-3 text-sm font-semibold text-white">{title}</h2>
            <div className="space-y-2">
                {entries.slice(0, 10).map((entry) => (
                    <div key={entry.path} className="rounded-lg bg-black/20 px-3 py-2">
                        <p className="text-sm text-gray-200">{entry.name}</p>
                        <p className="mt-1 break-all font-mono text-xs text-gray-500">{entry.path}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

function World() {
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [showPicker, setShowPicker] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [isScanning, setIsScanning] = useState(false);

    const summary = useMemo(() => summarizeWorld(result), [result]);
    const grouped = useMemo(() => groupUnitsByStatus(result?.units || []), [result]);

    const handleScan = () => {
        setError(null);
        setIsScanning(true);
        api.scanWorld(simsPath, {
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

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/30 p-3 text-cyan-200">
                            <Database size={26} />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-white">World</h1>
                            <p className="mt-1 text-sm text-gray-400">Local inventory and game-state evidence</p>
                        </div>
                    </div>
                </div>
                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                    <div className="min-w-0 md:w-[34rem]">
                        <label htmlFor="world-sims-path" className="mb-2 block text-sm font-medium text-gray-300">
                            Sims 4 folder
                        </label>
                        <div className="flex rounded-lg border border-gray-700 bg-gray-950/60">
                            <input
                                id="world-sims-path"
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
                        onClick={handleScan}
                        disabled={isScanning || !simsPath.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 font-medium text-gray-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isScanning ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
                        Scan World
                    </button>
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

            {result && (
                <>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                        <StatTile icon={Package} label="Active" value={summary.activeUnits} tone="emerald" />
                        <StatTile icon={ShieldAlert} label="Disabled" value={summary.disabledUnits} tone="amber" />
                        <StatTile icon={AlertTriangle} label="Quarantine" value={summary.quarantinedUnits} tone="red" />
                        <StatTile icon={Archive} label="Archive" value={summary.archivedUnits} tone="blue" />
                        <StatTile icon={HardDrive} label="Packages" value={summary.packageFiles} />
                        <StatTile icon={Database} label="Scripts" value={summary.scriptFiles} />
                    </div>

                    <div className="grid gap-4 lg:grid-cols-4">
                        <StatTile icon={Database} label="Tray" value={summary.trayFiles} />
                        <StatTile icon={Database} label="Saves" value={summary.saveFiles} />
                        <StatTile icon={Database} label="Logs" value={summary.logFiles} />
                        <StatTile icon={Database} label="Caches" value={summary.cacheFiles} />
                    </div>

                    {(result.warnings || []).length > 0 && (
                        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
                            <div className="flex items-start gap-3 text-amber-200">
                                <AlertTriangle size={18} className="mt-0.5 shrink-0" />
                                <div className="space-y-1">
                                    {result.warnings.map((warning) => (
                                        <p key={warning}>{warning}</p>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="grid gap-4 xl:grid-cols-2">
                        {GROUPS.map((group) => (
                            <UnitGroup key={group.key} group={group} units={grouped[group.key]} />
                        ))}
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                        <EvidenceList title="Crash Logs" entries={result.game_state?.logs || []} />
                        <EvidenceList title="Cache Artifacts" entries={result.game_state?.caches || []} />
                        <EvidenceList title="Tray Files" entries={result.game_state?.tray || []} />
                        <EvidenceList title="Save Files" entries={result.game_state?.saves || []} />
                    </div>
                </>
            )}

            {!result && !isScanning && (
                <div className="rounded-xl border border-gray-800 bg-gray-900/35 p-8 text-center text-gray-500">
                    <Database size={34} className="mx-auto mb-3 text-gray-600" />
                    <p>No world inventory loaded.</p>
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

export default World;
