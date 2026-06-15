import { useEffect, useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import {
    AlertTriangle,
    CheckCircle2,
    Database,
    FolderOpen,
    FolderTree,
    Info,
    Loader2,
    RefreshCw,
    Save,
    Settings as SettingsIcon,
    ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import FilePicker from '../components/FilePicker';
import {
    DEFAULT_SIMS4_PROFILE,
    buildProfileConfigPatch,
    deriveProfileFolders,
    normalizeProfileConfig,
} from './settingsModel';

const folderTone = {
    mods: 'border-blue-500/25 bg-blue-950/15 text-blue-100',
    tray: 'border-emerald-500/25 bg-emerald-950/15 text-emerald-100',
    saves: 'border-amber-500/25 bg-amber-950/15 text-amber-100',
    cache: 'border-gray-700 bg-gray-900/50 text-gray-200',
};

function ProfilePathField({ value, onChange, onBrowse, disabled }) {
    return (
        <div className="min-w-0">
            <label className="mb-2 block text-sm font-medium text-gray-300">Active Sims 4 profile</label>
            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                <input
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    disabled={disabled}
                    placeholder={DEFAULT_SIMS4_PROFILE}
                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
                />
                <button
                    type="button"
                    onClick={onBrowse}
                    disabled={disabled}
                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                    title="Choose active Sims 4 profile"
                    aria-label="Choose active Sims 4 profile"
                >
                    <FolderOpen size={18} />
                </button>
            </div>
        </div>
    );
}

function FolderRow({ folder }) {
    return (
        <div className={`min-w-0 rounded-lg border p-4 ${folderTone[folder.key] || folderTone.cache}`}>
            <div className="mb-2 flex items-center gap-2">
                <FolderTree size={17} />
                <span className="text-sm font-semibold text-white">{folder.label}</span>
            </div>
            <p className="break-all font-mono text-xs opacity-85">{folder.path}</p>
        </div>
    );
}

function KnownProfiles({ profiles, activeProfile, onSelect }) {
    if (profiles.length === 0) {
        return (
            <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-4 text-sm text-gray-500">
                No saved profiles yet.
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {profiles.map((profile) => {
                const isActive = profile === activeProfile;
                return (
                    <button
                        key={profile}
                        type="button"
                        onClick={() => onSelect(profile)}
                        className={`flex w-full min-w-0 items-center justify-between gap-3 rounded-lg border p-3 text-left transition ${isActive
                            ? 'border-blue-500/40 bg-blue-950/25 text-blue-100'
                            : 'border-gray-800 bg-gray-900/40 text-gray-300 hover:border-gray-700 hover:bg-gray-800/70'
                        }`}
                    >
                        <span className="min-w-0 break-all font-mono text-xs">{profile}</span>
                        {isActive && <CheckCircle2 className="shrink-0 text-blue-300" size={18} />}
                    </button>
                );
            })}
        </div>
    );
}

function BoundaryNote() {
    return (
        <section className="rounded-xl border border-emerald-500/25 bg-emerald-950/10 p-5">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-white">
                <ShieldCheck size={18} />
                Safety boundary
            </h2>
            <div className="space-y-2 text-sm text-emerald-100/80">
                <p>Saving a profile updates Simanalysis app config only.</p>
                <p>It does not move, enable, disable, quarantine, delete, or rewrite Sims files.</p>
            </div>
        </section>
    );
}

function Settings() {
    const [activeProfile, setActiveProfile] = useState(DEFAULT_SIMS4_PROFILE);
    const [knownProfiles, setKnownProfiles] = useState([]);
    const [showProfilePicker, setShowProfilePicker] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [configError, setConfigError] = useState(null);

    const folders = useMemo(() => deriveProfileFolders(activeProfile), [activeProfile]);

    useEffect(() => {
        let cancelled = false;

        async function loadConfig() {
            setIsLoading(true);
            setConfigError(null);
            try {
                const config = await invoke('get_config');
                if (cancelled) return;
                const normalized = normalizeProfileConfig(config);
                setActiveProfile(normalized.activeProfile);
                setKnownProfiles(normalized.profiles);
            } catch (error) {
                if (cancelled) return;
                const message = error instanceof Error ? error.message : String(error);
                setConfigError(message);
                const normalized = normalizeProfileConfig({});
                setActiveProfile(normalized.activeProfile);
                setKnownProfiles(normalized.profiles);
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        }

        loadConfig();
        return () => {
            cancelled = true;
        };
    }, []);

    const handleReload = async () => {
        setIsLoading(true);
        setConfigError(null);
        try {
            const config = await invoke('get_config');
            const normalized = normalizeProfileConfig(config);
            setActiveProfile(normalized.activeProfile);
            setKnownProfiles(normalized.profiles);
            toast.success('Profile config loaded');
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setConfigError(message);
            toast.error(`Profile config failed: ${message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSave = async () => {
        const patch = buildProfileConfigPatch(activeProfile, knownProfiles);
        setIsSaving(true);
        setConfigError(null);
        try {
            const savedConfig = await invoke('set_config', { patch });
            const normalized = normalizeProfileConfig(savedConfig);
            setActiveProfile(normalized.activeProfile);
            setKnownProfiles(normalized.profiles);
            toast.success('Active profile saved');
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setConfigError(message);
            toast.error(`Profile save failed: ${message}`);
        } finally {
            setIsSaving(false);
        }
    };

    const isBusy = isLoading || isSaving;

    return (
        <div className="min-w-0 space-y-6 p-4 md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3">
                        <div className="rounded-xl bg-blue-500/15 p-3 text-blue-200">
                            <SettingsIcon size={26} />
                        </div>
                        <div className="min-w-0">
                            <h1 className="text-3xl font-bold text-white">Settings</h1>
                            <p className="text-gray-400">Profile Manager Light and desktop state</p>
                        </div>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={handleReload}
                        disabled={isBusy}
                        className="flex h-10 items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 text-sm font-medium text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isLoading ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        Reload
                    </button>
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={isBusy}
                        className="flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                        Save Profile
                    </button>
                </div>
            </div>

            {configError && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-950/15 p-4 text-sm text-amber-100">
                    <div className="flex gap-3">
                        <AlertTriangle className="mt-0.5 shrink-0" size={18} />
                        <div className="min-w-0">
                            <p className="font-medium text-white">Desktop config is not available</p>
                            <p className="mt-1 break-words opacity-85">{configError}</p>
                        </div>
                    </div>
                </div>
            )}

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
                    <div className="min-w-0 space-y-4">
                        <div>
                            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                                <Database size={19} />
                                Active profile
                            </h2>
                            <p className="mt-1 text-sm text-gray-500">
                                The selected root is stored as app state; its Mods folder remains the legacy scan default.
                            </p>
                        </div>
                        <ProfilePathField
                            value={activeProfile}
                            onChange={setActiveProfile}
                            onBrowse={() => setShowProfilePicker(true)}
                            disabled={isBusy}
                        />
                    </div>
                    <div className="rounded-lg border border-blue-500/25 bg-blue-950/15 p-4 text-sm text-blue-100">
                        <h3 className="mb-2 flex items-center gap-2 font-semibold text-white">
                            <Info size={17} />
                            Profile Manager Light
                        </h3>
                        <p className="text-blue-100/80">
                            This release remembers your chosen Sims 4 root and derives its common folders. Full profile
                            switching, cross-view defaults, and file operations stay behind later Operating Table gates.
                        </p>
                    </div>
                </div>
            </section>

            <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                <div className="mb-4">
                    <h2 className="text-lg font-semibold text-white">Derived folders</h2>
                    <p className="mt-1 text-sm text-gray-500">Read-only path preview from the active profile.</p>
                </div>
                <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {folders.map((folder) => (
                        <FolderRow key={folder.key} folder={folder} />
                    ))}
                </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
                <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <div className="mb-4">
                        <h2 className="text-lg font-semibold text-white">Known profiles</h2>
                        <p className="mt-1 text-sm text-gray-500">Saved roots for quick selection.</p>
                    </div>
                    <KnownProfiles
                        profiles={knownProfiles}
                        activeProfile={activeProfile}
                        onSelect={setActiveProfile}
                    />
                </section>
                <BoundaryNote />
            </div>

            <FilePicker
                isOpen={showProfilePicker}
                onClose={() => setShowProfilePicker(false)}
                onSelect={setActiveProfile}
                initialPath={activeProfile}
            />
        </div>
    );
}

export default Settings;
