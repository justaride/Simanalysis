export const DEFAULT_SIMS4_PROFILE = '~/Documents/Electronic Arts/The Sims 4';

const PROFILE_CHILD_FOLDERS = new Set(['Mods', 'Tray', 'saves', 'Saves']);

function normalizePath(value) {
    if (typeof value !== 'string') return '';
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (trimmed === '/' || trimmed === '\\') return trimmed;
    return trimmed.replace(/[\\/]+$/, '') || trimmed;
}

function pathSegments(value) {
    return normalizePath(value).split(/[\\/]+/).filter(Boolean);
}

function pathSeparator(value) {
    return value.includes('\\') && !value.includes('/') ? '\\' : '/';
}

function joinPath(base, child) {
    const normalizedBase = normalizePath(base) || DEFAULT_SIMS4_PROFILE;
    const separator = pathSeparator(normalizedBase);
    return `${normalizedBase}${separator}${child}`;
}

function profileFromLastScanPath(value) {
    const normalized = normalizePath(value);
    if (!normalized) return '';
    const separator = pathSeparator(normalized);
    const segments = pathSegments(normalized);
    const last = segments.at(-1);
    if (!PROFILE_CHILD_FOLDERS.has(last)) {
        return normalized;
    }
    const withoutChild = segments.slice(0, -1).join(separator);
    if (normalized.startsWith(separator)) {
        return `${separator}${withoutChild}`;
    }
    return withoutChild;
}

function dedupeProfiles(candidates) {
    const seen = new Set();
    const profiles = [];
    for (const candidate of candidates) {
        const normalized = normalizePath(candidate);
        if (!normalized || seen.has(normalized)) continue;
        seen.add(normalized);
        profiles.push(normalized);
    }
    return profiles;
}

export function normalizeProfileConfig(config = {}) {
    const storedProfiles = Array.isArray(config.sims4_profiles) ? config.sims4_profiles : [];
    const activeProfile = normalizePath(config.active_sims4_profile)
        || profileFromLastScanPath(config.last_scan_path)
        || DEFAULT_SIMS4_PROFILE;
    const profiles = dedupeProfiles([activeProfile, ...storedProfiles]);

    return {
        activeProfile,
        profiles,
    };
}

export function deriveProfileFolders(activeProfile) {
    const profile = normalizePath(activeProfile) || DEFAULT_SIMS4_PROFILE;
    return [
        { key: 'mods', label: 'Mods', path: joinPath(profile, 'Mods') },
        { key: 'tray', label: 'Tray', path: joinPath(profile, 'Tray') },
        { key: 'saves', label: 'Saves', path: joinPath(profile, 'saves') },
        { key: 'cache', label: 'Cache', path: profile },
    ];
}

export function buildProfileConfigPatch(activeProfile, existingProfiles = []) {
    const profile = normalizePath(activeProfile) || DEFAULT_SIMS4_PROFILE;
    return {
        active_sims4_profile: profile,
        sims4_profiles: dedupeProfiles([profile, ...existingProfiles]),
        last_scan_path: joinPath(profile, 'Mods'),
    };
}
