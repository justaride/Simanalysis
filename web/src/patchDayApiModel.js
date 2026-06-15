function optionalTrimmedPath(value) {
    const path = String(value || '').trim();
    return path || null;
}

export function patchDayOptions(options = {}) {
    const result = {};
    const state = optionalTrimmedPath(options.state);
    if (state) {
        result.state = state;
    }
    return result;
}
