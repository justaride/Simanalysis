const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    missing_staging_folder: ['Missing staging folder', 'red'],
    no_staged_files_found: ['No staged files found', 'green'],
};

const KIND_ORDER = {
    archive: 0,
    package: 1,
    script: 2,
    other: 3,
};

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

function words(value) {
    return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatUpdateBytes(bytes) {
    const value = Number.isFinite(bytes) ? bytes : 0;
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function summarizeUpdateDeskStatus(payload = {}) {
    const [statusLabel, tone] = STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        stagingPath: payload.staging_path || null,
        itemCount: count(payload.item_count),
        archiveCount: count(payload.archive_count),
        packageCount: count(payload.package_count),
        scriptCount: count(payload.script_count),
        otherCount: count(payload.other_count),
        sourceBoundCount: count(payload.source_bound_count),
        missingSourceCount: count(payload.missing_source_count),
        totalSizeBytes: count(payload.total_size_bytes),
        totalSizeLabel: formatUpdateBytes(payload.total_size_bytes),
        latestModifiedAt: payload.latest_modified_at || null,
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        signalCount: Array.isArray(payload.signals) ? payload.signals.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
    };
}

export function toUpdateItemRows(payload = {}) {
    const items = Array.isArray(payload.items) ? payload.items : [];
    return items.map((item) => {
        const sourceStatus = item.source_binding?.status || 'unknown';
        const archiveStatus = item.archive_scan?.status || 'not_archive';
        return {
            id: item.relative_path || item.name || 'staged-item',
            name: item.name || 'Unknown item',
            kind: item.kind || 'other',
            kindLabel: words(item.kind),
            extension: item.extension || '',
            sourceStatus,
            sourceLabel: words(sourceStatus),
            archiveStatus,
            archiveLabel: words(archiveStatus),
            memberCount: Number.isFinite(item.archive_scan?.member_count)
                ? item.archive_scan.member_count
                : null,
            sizeBytes: count(item.size_bytes),
            sizeLabel: formatUpdateBytes(item.size_bytes),
            latestModifiedAt: item.modified_at || null,
        };
    }).sort((left, right) => {
        const leftOrder = KIND_ORDER[left.kind] ?? KIND_ORDER.other;
        const rightOrder = KIND_ORDER[right.kind] ?? KIND_ORDER.other;
        if (leftOrder !== rightOrder) return leftOrder - rightOrder;
        return left.name.localeCompare(right.name);
    });
}

export function toUpdateSignalRows(payload = {}) {
    const signals = Array.isArray(payload.signals) ? payload.signals : [];
    return signals.map((signal, index) => ({
        id: `${signal.id || 'signal'}-${index}`,
        label: words(signal.id),
        severity: signal.severity || 'unknown',
        severityLabel: words(signal.severity),
        message: signal.message || '',
        location: signal.path || '',
        detail: Array.isArray(signal.paths) ? signal.paths.join(', ') : '',
    }));
}
