export function cacheDoctorOptions() {
    return {};
}

export function cacheCleanupPlanOptions(options = {}) {
    const exportPath = String(options.exportPath || '').trim();
    if (!exportPath) {
        throw new Error('cacheCleanupPlan requires exportPath');
    }
    return { exportPath };
}

export function cacheCleanupApplyOptions(options = {}) {
    const actions = Array.isArray(options.actions)
        ? options.actions.map((action) => String(action || '').trim()).filter(Boolean)
        : [];
    const allActions = Boolean(options.allActions);
    if (actions.length > 0 && allActions) {
        throw new Error('Choose actions or allActions, not both');
    }
    if (actions.length === 0 && !allActions) {
        throw new Error('cacheCleanupApply requires at least one action or allActions');
    }
    return { actions, allActions };
}

export function cacheCleanupRestoreOptions() {
    return {};
}

export function cacheOperationStatusOptions() {
    return {};
}
