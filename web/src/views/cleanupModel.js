const CATEGORY_LABELS = {
    exact_duplicate: 'Exact Duplicates',
    inactive_archive: 'Archives',
    duplicate_resource_cfg: 'Resource.cfg',
    support_file: 'Support Files',
    misplaced_tray: 'Tray Files',
};

const APPLICABLE_STATUSES = new Set(['planned', 'partial']);
const APPLICABLE_ACTION_STATUSES = new Set(['pending', 'blocked']);
const RESTORABLE_STATUSES = new Set(['applied', 'partial', 'restoring']);
const RESTORABLE_ACTION_STATUSES = new Set(['moving', 'moved', 'restore_pending', 'restoring']);

function count(summary, key) {
    return Number.isFinite(summary?.[key]) ? summary[key] : 0;
}

function asArray(value) {
    return Array.isArray(value) ? value : [];
}

export function cleanupCategoryLabel(category) {
    return CATEGORY_LABELS[category] || String(category || 'unknown').replaceAll('_', ' ');
}

export function summarizeCleanupPlan(plan = {}) {
    const summary = plan.summary || {};
    return {
        planId: plan.plan_id || null,
        rootPath: plan.root_path || null,
        dbPath: plan.db_path || null,
        filesConsidered: count(summary, 'files_considered'),
        findingCount: count(summary, 'finding_count'),
        actionCount: count(summary, 'action_count'),
        duplicateGroups: count(summary, 'duplicate_groups'),
        archives: count(summary, 'archives'),
        duplicateResourceCfg: count(summary, 'duplicate_resource_cfg'),
        supportFiles: count(summary, 'support_files'),
        misplacedTray: count(summary, 'misplaced_tray'),
        warnings: Array.isArray(plan.warnings) ? plan.warnings : [],
    };
}

export function flattenCleanupActions(plan = {}) {
    const findings = asArray(plan.findings);
    return findings.flatMap((finding) => {
        const actions = asArray(finding.actions);
        const evidence = finding.evidence || {};
        return actions.map((action) => ({
            id: action.action_id || '',
            kind: action.kind || '',
            category: finding.category || 'unknown',
            categoryLabel: cleanupCategoryLabel(finding.category),
            title: finding.title || cleanupCategoryLabel(finding.category),
            severity: finding.severity || 'review',
            source: action.source_relative_path || '',
            destination: action.proposed_destination || '',
            reason: action.reason || finding.explanation || '',
            keepCandidate: evidence.keep_candidate || null,
        }));
    });
}

export function selectAllCleanupActions(actions = []) {
    return asArray(actions)
        .map((action) => action?.id)
        .filter(Boolean);
}

export function toggleCleanupAction(selectedIds = [], actionId, checked) {
    const next = new Set(asArray(selectedIds).filter(Boolean));
    if (!actionId) {
        return [...next];
    }
    if (checked) {
        next.add(actionId);
    } else {
        next.delete(actionId);
    }
    return [...next];
}

export function canStageCleanupOperation({
    planPath = '',
    selectedActionIds = [],
    allActions = false,
    actionCount = 0,
} = {}) {
    const selectedCount = asArray(selectedActionIds).length;
    if (!String(planPath).trim() || actionCount <= 0) {
        return false;
    }
    if (allActions && selectedCount > 0) {
        return false;
    }
    return allActions || selectedCount > 0;
}

export function summarizeCleanupOperation(manifest = {}) {
    const actions = asArray(manifest.actions);
    const statusCounts = {};
    const errors = [];
    for (const action of actions) {
        const status = String(action?.status || 'unknown');
        statusCounts[status] = (statusCounts[status] || 0) + 1;
        if (action?.error) {
            errors.push(String(action.error));
        }
    }
    return {
        operationId: manifest.operation_id || null,
        manifestPath: manifest.manifest_path || null,
        status: manifest.status || null,
        actionCount: actions.length,
        statusCounts,
        warnings: asArray(manifest.warnings),
        blockers: asArray(manifest.blockers),
        errors,
    };
}

export function canApplyCleanupOperation(manifest = {}) {
    const actions = asArray(manifest.actions);
    return (
        APPLICABLE_STATUSES.has(manifest.status)
        && actions.some((action) => APPLICABLE_ACTION_STATUSES.has(action?.status))
    );
}

export function canRestoreCleanupOperation(manifest = {}) {
    const actions = asArray(manifest.actions);
    return (
        RESTORABLE_STATUSES.has(manifest.status)
        && actions.some((action) => RESTORABLE_ACTION_STATUSES.has(action?.status))
    );
}
