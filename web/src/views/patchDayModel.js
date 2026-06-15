import { DEFAULT_SIMS4_PROFILE, normalizeProfileConfig } from './settingsModel.js';

const STATUS_LABELS = {
    changed: ['Patch detected', 'amber'],
    unchanged: ['No patch change', 'green'],
    unrecorded: ['No baseline recorded', 'blue'],
    missing_game_version: ['GameVersion.txt missing', 'red'],
    recorded: ['Baseline recorded', 'green'],
};

const RISK_STATUS_LABELS = {
    unknown_after_patch: 'Unknown after patch',
};

export function summarizePatchDayStatus(status = {}) {
    const [statusLabel, tone] = STATUS_LABELS[status.status] || ['Unknown', 'blue'];
    return {
        status: status.status || 'unknown',
        statusLabel,
        tone,
        patchDetected: Boolean(status.patch_detected),
        currentVersion: status.current_game_version || 'unknown',
        lastKnownVersion: status.last_known_game_version || 'none',
        riskCount: Array.isArray(status.risk_classes) ? status.risk_classes.length : 0,
        recommendationCount: Array.isArray(status.recommendations) ? status.recommendations.length : 0,
        warningCount: Array.isArray(status.warnings) ? status.warnings.length : 0,
        automaticReenableLabel: status.automatic_reenable ? 'Automatic re-enable enabled' : 'No automatic re-enable',
    };
}

export function toPatchRiskRows(status = {}) {
    const risks = Array.isArray(status.risk_classes) ? status.risk_classes : [];
    return risks.map((risk) => ({
        id: risk.id || risk.label || 'risk',
        label: risk.label || risk.id || 'Unknown risk',
        status: risk.status || 'unknown',
        statusLabel: RISK_STATUS_LABELS[risk.status] || risk.status || 'Unknown',
        reason: risk.reason || '',
    }));
}

export function canRecordPatchBaseline(status = {}) {
    return Boolean(status.current_game_version);
}

function normalizePath(value) {
    if (typeof value !== 'string') return '';
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (trimmed === '/' || trimmed === '\\') return trimmed;
    return trimmed.replace(/[\\/]+$/, '') || trimmed;
}

export function summarizePatchProfileWorkflow(status = {}, profileConfig = {}, selectedPath = '') {
    const normalizedConfig = normalizeProfileConfig(profileConfig);
    const activeProfile = normalizedConfig.activeProfile || DEFAULT_SIMS4_PROFILE;
    const selectedProfile = normalizePath(selectedPath) || activeProfile;
    const profileMatchesSelected = normalizePath(activeProfile) === selectedProfile;
    const patchDetected = Boolean(status.patch_detected);
    const riskCount = Array.isArray(status.risk_classes) ? status.risk_classes.length : 0;

    let safeActionTitle = 'Verify profile before recording';
    let safeActionBody = 'Confirm the selected Sims 4 folder is the profile you want to use for this Patch Day baseline.';
    if (patchDetected || riskCount > 0) {
        safeActionTitle = 'Use a separate test profile';
        safeActionBody = 'Keep unknown-after-patch mods disabled in your main profile until a vanilla test and save-copy test pass.';
    } else if (status.status === 'unchanged' && profileMatchesSelected) {
        safeActionTitle = 'Keep current profile guidance';
        safeActionBody = 'No game-version change is detected for the active profile; keep automatic re-enable off unless later manifest-backed profile operations exist.';
    } else if (status.status === 'unrecorded' && profileMatchesSelected) {
        safeActionTitle = 'Record only after confirming profile';
        safeActionBody = 'Recording a baseline writes Simanalysis state only and does not enable, disable, move, or delete mods.';
    }

    return {
        activeProfile,
        selectedProfile,
        profileMatchesSelected,
        knownProfileCount: normalizedConfig.profiles.length,
        profileStatusLabel: profileMatchesSelected ? 'Active profile selected' : 'Different folder selected',
        profileTone: profileMatchesSelected ? 'green' : 'amber',
        safeActionTitle,
        safeActionBody,
        cacheRecommendationTitle: patchDetected || riskCount > 0
            ? 'Run Cache Doctor after the patch test'
            : 'Cache Doctor optional',
        cacheRecommendationBody: patchDetected || riskCount > 0
            ? 'Review cache status and use reversible quarantine only after the game is closed and the patch test path is clear.'
            : 'Cache review can stay read-only unless symptoms suggest stale thumbnails or cache state.',
        automaticReenableLabel: status.automatic_reenable
            ? 'Automatic re-enable enabled'
            : 'No automatic re-enable',
    };
}
