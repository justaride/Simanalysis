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
