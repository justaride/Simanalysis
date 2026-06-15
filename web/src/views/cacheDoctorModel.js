const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    no_cache_targets_found: ['No cache targets found', 'green'],
};

const PLAN_STATUS_LABELS = {
    ready_for_review: ['Ready for review', 'green'],
    blocked: ['Blocked', 'red'],
    empty: ['Empty', 'blue'],
};

const OPERATION_STATUS_LABELS = {
    planned: ['Planned', 'blue'],
    applying: ['Applying', 'amber'],
    applied: ['Applied', 'green'],
    partial: ['Partial', 'amber'],
    restoring: ['Restoring', 'amber'],
    restored: ['Restored', 'blue'],
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

export function summarizeCacheCleanupPlan(payload = {}) {
    const [statusLabel, tone] = PLAN_STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        planId: payload.plan_id || null,
        generatedAt: payload.generated_at || null,
        rootPath: payload.root_path || null,
        manifestPath: payload.manifest_path || null,
        actionCount: count(payload.action_count),
        blockedCount: count(payload.blocked_count),
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        requiresSnapshotLabel: payload.requires_snapshot ? 'Snapshot required' : 'Snapshot not required',
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
    };
}

export function toCachePlanActionRows(payload = {}) {
    const actions = Array.isArray(payload.actions) ? payload.actions : [];
    return actions.map((action, index) => ({
        id: action.action_id || `cache-action-${index}`,
        type: action.action_type || 'unknown',
        typeLabel: words(action.action_type),
        targetId: action.target_id || 'unknown',
        label: action.label || action.source_relative_path || 'Cache target',
        status: action.status || 'unknown',
        statusLabel: words(action.status),
        sourceRelativePath: action.source_relative_path || '',
        quarantineRelativePath: action.quarantine_relative_path || '',
        expectedSizeLabel: formatCacheBytes(action.expected?.size),
        expectedItemCount: count(action.expected?.item_count),
        riskLabel: words(action.risk),
        blockers: Array.isArray(action.blockers) ? action.blockers : [],
    }));
}

export function getEligibleCacheActionRows(rows = []) {
    return rows.filter((row) => row.type === 'quarantine_cache_target' && row.status === 'planned');
}

export function toggleCacheActionSelection(current = [], actionId, checked) {
    const normalized = String(actionId || '').trim();
    if (!normalized) return current;
    if (checked) {
        return current.includes(normalized) ? current : [...current, normalized];
    }
    return current.filter((id) => id !== normalized);
}

export function selectAllCacheActions(rows = []) {
    return getEligibleCacheActionRows(rows).map((row) => row.id);
}

export function canApplyCachePlan({
    planPath,
    selectedActionIds = [],
    eligibleActionCount = 0,
} = {}) {
    return Boolean(
        String(planPath || '').trim()
        && selectedActionIds.length > 0
        && eligibleActionCount > 0,
    );
}

export function summarizeCacheOperation(payload = {}) {
    const [statusLabel, tone] = OPERATION_STATUS_LABELS[payload.status] || ['No operation', 'blue'];
    const actions = Array.isArray(payload.actions) ? payload.actions : [];
    return {
        operationId: payload.operation_id || null,
        status: payload.status || 'none',
        statusLabel,
        tone,
        manifestPath: payload.manifest_path || null,
        quarantinedCount: actions.filter((action) => action.status === 'quarantined').length,
        restoredCount: actions.filter((action) => action.status === 'restored').length,
        blockedCount: actions.filter((action) => action.status === 'blocked').length,
        canRestore: ['applied', 'partial', 'restoring'].includes(payload.status)
            && actions.some((action) => action.status === 'quarantined'),
    };
}
