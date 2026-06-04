export function summarizeFixPlan(data = {}) {
    const summary = data?.summary || {};
    return {
        actions: summary.actions || 0,
        high: summary.high || 0,
        medium: summary.medium || 0,
        low: summary.low || 0,
        warnings: summary.warnings || 0,
        blockers: summary.blockers || 0,
    };
}

export function groupActionsBySeverity(actions = []) {
    const grouped = {
        high: [],
        medium: [],
        low: [],
        unknown: [],
    };

    actions.forEach((action) => {
        if (grouped[action.severity]) {
            grouped[action.severity].push(action);
            return;
        }
        grouped.unknown.push(action);
    });

    return grouped;
}

export function getFixActionAffordance(action = {}) {
    const canApplyCacheCleanup =
        action?.kind === 'cache_cleanup_candidate' &&
        action?.can_apply === true &&
        action?.proposed_operation === 'move_to_simanalysis_cache_backup';

    if (canApplyCacheCleanup) {
        return {
            actionKind: 'cache_cleanup',
            badge: 'Manifest-backed',
            label: 'Move Cache to Backup',
            tone: 'emerald',
        };
    }

    return {
        actionKind: null,
        badge: 'Review-only',
        label: null,
        tone: 'cyan',
    };
}

export function summarizeFixSession(session = {}) {
    const status = session?.status || 'none';
    const manifestPath = session?.manifest_path || null;
    const recordCount = Array.isArray(session?.records) ? session.records.length : 0;

    return {
        canRestore: Boolean(manifestPath && status !== 'restored'),
        manifestPath,
        recordCount,
        status,
    };
}
