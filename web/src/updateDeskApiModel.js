export function updateDeskOptions() {
    return {};
}

export function updateDeskPlanOptions(modsPath, options = {}) {
    const trimmedModsPath = String(modsPath || '').trim();
    if (!trimmedModsPath) {
        throw new Error('updateDeskPlan requires modsPath');
    }
    const trimmedExportPath = String(options.exportPath || '').trim();
    return trimmedExportPath
        ? { modsPath: trimmedModsPath, exportPath: trimmedExportPath }
        : { modsPath: trimmedModsPath };
}

export function updateDeskCommitOptions(options = {}) {
    const actions = Array.isArray(options.actions)
        ? options.actions.map((action) => String(action || '').trim()).filter(Boolean)
        : [];
    const allActions = Boolean(options.allActions);
    if (actions.length > 0 && allActions) {
        throw new Error('Choose actions or allActions, not both');
    }
    if (actions.length === 0 && !allActions) {
        throw new Error('updateDeskCommit requires at least one action or allActions');
    }
    return { actions, allActions };
}

export function updateDeskUndoOptions() {
    return {};
}

export function updateDeskOperationStatusOptions() {
    return {};
}
