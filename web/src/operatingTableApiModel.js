export function cleanupStageOptions(options = {}) {
    if (!options.planPath) {
        throw new Error('cleanupStage requires planPath');
    }
    const actions = Array.isArray(options.actions) ? options.actions : [];
    const allActions = Boolean(options.allActions);
    if (actions.length > 0 && allActions) {
        throw new Error('Choose either selected actions or allActions');
    }
    return {
        planPath: options.planPath,
        actions,
        allActions,
    };
}
