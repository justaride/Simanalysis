const STATUS_LABELS = {
    review_recommended: ['Review recommended', 'amber'],
    missing_staging_folder: ['Missing staging folder', 'red'],
    no_staged_files_found: ['No staged files found', 'green'],
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
    blocked: ['Blocked', 'red'],
    undoing: ['Undoing', 'amber'],
    undone: ['Undone', 'blue'],
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

export function summarizeUpdateInstallPlan(payload = {}) {
    const [statusLabel, tone] = PLAN_STATUS_LABELS[payload.status] || ['Unknown', 'blue'];
    return {
        status: payload.status || 'unknown',
        statusLabel,
        tone,
        planId: payload.plan_id || null,
        generatedAt: payload.generated_at || null,
        stagingPath: payload.staging_path || null,
        modsPath: payload.mods_path || null,
        manifestPath: payload.manifest_path || null,
        actionCount: count(payload.action_count),
        copyCount: count(payload.copy_count),
        archiveReviewCount: count(payload.archive_review_count),
        blockedCount: count(payload.blocked_count),
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        recommendationCount: Array.isArray(payload.recommendations) ? payload.recommendations.length : 0,
        requiresSnapshotLabel: payload.requires_snapshot ? 'Snapshot required' : 'Snapshot not required',
        readOnlyLabel: payload.mutates_files ? 'Mutation reported' : 'Read-only',
        modsMutationLabel: payload.mutates_mods ? 'Mods mutation reported' : 'No Mods mutation',
    };
}

export function toUpdatePlanActionRows(payload = {}) {
    const actions = Array.isArray(payload.actions) ? payload.actions : [];
    return actions.map((action, index) => {
        const sourceStatus = action.source_binding?.status || 'unknown';
        const archiveStatus = action.archive_scan?.status || 'not_archive';
        return {
            id: action.action_id || `update-action-${index}`,
            type: action.action_type || 'unknown',
            typeLabel: words(action.action_type),
            status: action.status || 'unknown',
            statusLabel: words(action.status),
            sourceName: action.source_name || 'Unknown source',
            sourceRelativePath: action.source_relative_path || '',
            destinationRelativePath: action.destination_relative_path || 'Review archive contents',
            expectedSizeLabel: formatUpdateBytes(action.expected?.size),
            sourceStatus,
            sourceLabel: words(sourceStatus),
            archiveStatus,
            archiveLabel: words(archiveStatus),
            blockers: Array.isArray(action.blockers) ? action.blockers : [],
            reviewNotes: Array.isArray(action.review_notes) ? action.review_notes : [],
        };
    });
}

export function getCommitEligibleUpdateActionRows(rows = []) {
    return rows.filter((row) => row.type === 'copy_staged_file' && row.status === 'planned');
}

export function toggleUpdateActionSelection(current = [], actionId, checked) {
    const normalized = String(actionId || '').trim();
    if (!normalized) return current;
    if (checked) {
        return current.includes(normalized) ? current : [...current, normalized];
    }
    return current.filter((id) => id !== normalized);
}

export function canCommitUpdatePlan({
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

export function summarizeUpdateOperation(payload = {}) {
    const [statusLabel, tone] = OPERATION_STATUS_LABELS[payload.status] || ['No operation', 'blue'];
    const actions = Array.isArray(payload.actions) ? payload.actions : [];
    return {
        operationId: payload.operation_id || null,
        status: payload.status || 'none',
        statusLabel,
        tone,
        manifestPath: payload.manifest_path || null,
        copiedCount: actions.filter((action) => action.status === 'copied').length,
        blockedCount: actions.filter((action) => action.status === 'blocked').length,
        undoneCount: actions.filter((action) => action.status === 'undone').length,
        warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
        blockerCount: Array.isArray(payload.blockers) ? payload.blockers.length : 0,
        canUndo: ['applying', 'applied', 'partial', 'undoing'].includes(payload.status),
    };
}
