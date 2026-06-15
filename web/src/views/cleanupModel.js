const CATEGORY_LABELS = {
    exact_duplicate: 'Exact Duplicates',
    inactive_archive: 'Archives',
    duplicate_resource_cfg: 'Resource.cfg',
    support_file: 'Support Files',
    misplaced_tray: 'Tray Files',
};

function count(summary, key) {
    return Number.isFinite(summary?.[key]) ? summary[key] : 0;
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
    const findings = Array.isArray(plan.findings) ? plan.findings : [];
    return findings.flatMap((finding) => {
        const actions = Array.isArray(finding.actions) ? finding.actions : [];
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
