const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    no_cache_targets_found: ['No cache targets found', 'green'],
};

const STATUS_TEXT = {
    present: 'Present',
    absent: 'Absent',
    skipped_symlink: 'Skipped symlink',
    unexpected_type: 'Unexpected type',
};

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

function words(value) {
    return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatCacheBytes(bytes) {
    const value = Number.isFinite(bytes) ? bytes : 0;
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function summarizeCacheStatus(payload = {}) {
    const [statusLabel, tone] = STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        rootPath: payload.root_path || null,
        presentCount: count(payload.present_count),
        totalSizeBytes: count(payload.total_size_bytes),
        totalSizeLabel: formatCacheBytes(payload.total_size_bytes),
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
    };
}

export function toCacheTargetRows(payload = {}) {
    const targets = Array.isArray(payload.targets) ? payload.targets : [];
    return targets.map((target) => ({
        id: target.id || target.relative_path || 'cache-target',
        label: target.label || target.relative_path || 'Cache target',
        relativePath: target.relative_path || '',
        kindLabel: words(target.kind),
        riskLabel: words(target.risk),
        reason: target.reason || '',
        present: Boolean(target.present),
        status: target.status || 'unknown',
        statusLabel: STATUS_TEXT[target.status] || words(target.status),
        sizeBytes: count(target.size_bytes),
        sizeLabel: formatCacheBytes(target.size_bytes),
        itemCount: count(target.item_count),
        modifiedAt: target.modified_at || null,
    })).sort((left, right) => {
        if (left.present !== right.present) return left.present ? -1 : 1;
        return left.relativePath.localeCompare(right.relativePath);
    });
}
