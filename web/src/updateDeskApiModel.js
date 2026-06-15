export function updateDeskOptions() {
    return {};
}

export function updateDeskPlanOptions(modsPath) {
    const trimmedModsPath = String(modsPath || '').trim();
    if (!trimmedModsPath) {
        throw new Error('updateDeskPlan requires modsPath');
    }
    return { modsPath: trimmedModsPath };
}
