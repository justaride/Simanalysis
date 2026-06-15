import { DEFAULT_SIMS4_PROFILE, normalizeProfileConfig } from './settingsModel.js';

const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    missing_saves_folder: ['Missing saves folder', 'red'],
    no_save_files_found: ['No save files found', 'green'],
};

const GUIDANCE_STATUS_LABELS = {
    test_copy_recommended: ['Test copy recommended', 'amber'],
    missing_evidence: ['Missing evidence', 'amber'],
    read_only_review: ['Read-only review', 'blue'],
    no_saves_loaded: ['No saves loaded', 'blue'],
};

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

function words(value) {
    return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatSaveBytes(bytes) {
    const value = Number.isFinite(bytes) ? bytes : 0;
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function summarizeSaveProtectorStatus(payload = {}) {
    const [statusLabel, tone] = STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        rootPath: payload.root_path || null,
        savesPath: payload.saves_path || null,
        primarySaveCount: count(payload.primary_save_count),
        backupCount: count(payload.backup_count),
        orphanBackupCount: count(payload.orphan_backup_count),
        totalSizeBytes: count(payload.total_size_bytes),
        totalSizeLabel: formatSaveBytes(payload.total_size_bytes),
        latestModifiedAt: payload.latest_modified_at || null,
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        signalCount: Array.isArray(payload.signals) ? payload.signals.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
    };
}

export function toSaveGroupRows(payload = {}) {
    const groups = Array.isArray(payload.save_groups) ? payload.save_groups : [];
    return groups.map((group) => {
        const primary = group.primary || null;
        return {
            id: group.slot || primary?.relative_path || 'save-group',
            slot: group.slot || 'Unknown slot',
            primaryName: primary?.name || 'No primary save',
            primaryPath: primary?.relative_path || '',
            hasPrimary: Boolean(primary),
            backupCount: count(group.backup_count),
            totalSizeBytes: count(group.total_size_bytes),
            totalSizeLabel: formatSaveBytes(group.total_size_bytes),
            latestModifiedAt: group.latest_modified_at || null,
        };
    }).sort((left, right) => {
        if (left.hasPrimary !== right.hasPrimary) return left.hasPrimary ? -1 : 1;
        return left.slot.localeCompare(right.slot);
    });
}

export function toSaveSignalRows(payload = {}) {
    const signals = Array.isArray(payload.signals) ? payload.signals : [];
    return signals.map((signal, index) => ({
        id: `${signal.id || 'signal'}-${index}`,
        label: words(signal.id),
        severity: signal.severity || 'unknown',
        severityLabel: words(signal.severity),
        message: signal.message || '',
        location: signal.path || (Array.isArray(signal.paths) ? signal.paths.join(', ') : ''),
    }));
}

function normalizePath(value) {
    if (typeof value !== 'string') return '';
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (trimmed === '/' || trimmed === '\\') return trimmed;
    return trimmed.replace(/[\\/]+$/, '') || trimmed;
}

function patchEvidenceLabel(patchStatus = {}) {
    const risks = Array.isArray(patchStatus.risk_classes) ? patchStatus.risk_classes : [];
    if (risks.some((risk) => risk.status === 'unknown_after_patch') || patchStatus.patch_detected) {
        return 'Unknown after patch';
    }
    if (patchStatus.status === 'unchanged' || patchStatus.status === 'recorded') {
        return 'No patch change detected';
    }
    if (patchStatus.status === 'missing_game_version') {
        return 'Game version missing';
    }
    return 'Patch evidence missing';
}

export function summarizeSaveLaunchGuidance(
    saveStatus = {},
    profileConfig = {},
    patchStatus = {},
    selectedPath = '',
) {
    const normalizedConfig = normalizeProfileConfig(profileConfig);
    const activeProfile = normalizedConfig.activeProfile || DEFAULT_SIMS4_PROFILE;
    const selectedProfile = normalizePath(selectedPath) || normalizePath(saveStatus.root_path) || activeProfile;
    const profileMatchesSelected = normalizePath(activeProfile) === selectedProfile;
    const patchLabel = patchEvidenceLabel(patchStatus);
    const saveCount = count(saveStatus.primary_save_count);
    const missingPatchEvidence = patchLabel === 'Patch evidence missing'
        || patchLabel === 'Game version missing';
    const unknownAfterPatch = patchLabel === 'Unknown after patch';
    let status = 'read_only_review';

    if (saveCount === 0 && !saveStatus.status) {
        status = 'no_saves_loaded';
    } else if (!profileMatchesSelected || missingPatchEvidence) {
        status = 'missing_evidence';
    } else if (unknownAfterPatch) {
        status = 'test_copy_recommended';
    }

    const [statusLabel, tone] = GUIDANCE_STATUS_LABELS[status] || ['Read-only review', 'blue'];
    let launchTitle = 'Review before launch';
    let launchBody = 'Save Protector has read-only save evidence, but it does not guarantee mod compatibility.';
    if (status === 'test_copy_recommended') {
        launchTitle = 'Launch only with a save copy';
        launchBody = 'These saves are likely tied to the active profile, but patch evidence is unknown-after-patch. Use a copied save for testing before opening important saves.';
    } else if (status === 'missing_evidence') {
        launchTitle = 'Resolve missing evidence before launch';
        launchBody = 'Profile or patch evidence is missing, so Save Protector cannot say whether these saves match the active mod state.';
    } else if (status === 'no_saves_loaded') {
        launchTitle = 'Load save status first';
        launchBody = 'Run Save Protector status before using launch guidance.';
    }

    return {
        status,
        statusLabel,
        tone,
        profileStatusLabel: profileMatchesSelected ? 'Active profile selected' : 'Different folder selected',
        profileTone: profileMatchesSelected ? 'green' : 'amber',
        activeProfile,
        selectedProfile,
        patchEvidenceLabel: patchLabel,
        launchTitle,
        launchBody,
        actionItems: [
            'Keep the original save files read-only in Simanalysis.',
            'Use a manual copy or future manifest-backed test-copy workflow before launch.',
            'Do not assume missing mods are safe after a game patch.',
        ],
    };
}
