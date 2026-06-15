const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    missing_saves_folder: ['Missing saves folder', 'red'],
    no_save_files_found: ['No save files found', 'green'],
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
