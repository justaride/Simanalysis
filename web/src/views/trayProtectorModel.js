const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    missing_tray_folder: ['Missing Tray folder', 'red'],
    no_tray_files_found: ['No Tray files found', 'green'],
};

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

function words(value) {
    return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dependencyKindLabel(value) {
    if (value === 'cas') return 'CAS';
    if (value === 'build_buy') return 'Build/Buy';
    return words(value);
}

export function formatTrayBytes(bytes) {
    const value = Number.isFinite(bytes) ? bytes : 0;
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function summarizeTrayProtectorStatus(payload = {}) {
    const [statusLabel, tone] = STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        rootPath: payload.root_path || null,
        trayPath: payload.tray_path || null,
        trayFileCount: count(payload.tray_file_count),
        groupCount: count(payload.group_count),
        anchoredGroupCount: count(payload.anchored_group_count),
        sidecarOnlyGroupCount: count(payload.sidecar_only_group_count),
        totalSizeBytes: count(payload.total_size_bytes),
        totalSizeLabel: formatTrayBytes(payload.total_size_bytes),
        latestModifiedAt: payload.latest_modified_at || null,
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        signalCount: Array.isArray(payload.signals) ? payload.signals.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
    };
}

export function toTrayGroupRows(payload = {}) {
    const groups = Array.isArray(payload.groups) ? payload.groups : [];
    return groups.map((group) => ({
        id: group.stem || 'tray-group',
        stem: group.stem || 'Unknown group',
        anchorLabel: group.has_trayitem ? 'Anchored' : 'Sidecar only',
        hasTrayitem: Boolean(group.has_trayitem),
        typeHint: group.type_hint || 'Unknown',
        fileCount: count(group.file_count),
        extensionsLabel: Array.isArray(group.extensions) && group.extensions.length
            ? group.extensions.join(', ')
            : 'none',
        totalSizeBytes: count(group.total_size_bytes),
        totalSizeLabel: formatTrayBytes(group.total_size_bytes),
        latestModifiedAt: group.latest_modified_at || null,
    })).sort((left, right) => {
        if (left.hasTrayitem !== right.hasTrayitem) return left.hasTrayitem ? -1 : 1;
        return left.stem.localeCompare(right.stem);
    });
}

export function toTraySignalRows(payload = {}) {
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

export function toTrayDependencyRows(payload = {}) {
    const groups = Array.isArray(payload.groups) ? payload.groups : [];
    return groups.flatMap((group) => {
        const signals = Array.isArray(group.dependency_signals) ? group.dependency_signals : [];
        return signals.map((signal, index) => ({
            id: `${group.stem || 'tray-group'}-${signal.id || 'dependency'}-${index}`,
            group: group.stem || 'Unknown group',
            dependencyKind: dependencyKindLabel(signal.dependency_kind),
            confidence: signal.confidence || 'unknown',
            confidenceLabel: words(signal.confidence),
            anchorState: signal.anchor_state || 'unknown',
            severity: signal.severity || 'unknown',
            severityLabel: words(signal.severity),
            message: signal.message || '',
            evidenceLabel: Array.isArray(signal.evidence) && signal.evidence.length
                ? signal.evidence.join('; ')
                : 'No evidence listed',
        }));
    }).sort((left, right) => {
        const confidenceOrder = { likely: 0, probable: 1, unknown: 2 };
        const leftOrder = confidenceOrder[left.confidence] ?? 3;
        const rightOrder = confidenceOrder[right.confidence] ?? 3;
        if (leftOrder !== rightOrder) return leftOrder - rightOrder;
        return left.group.localeCompare(right.group);
    });
}
