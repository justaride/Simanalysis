export function cleanupPlanOptions(options = {}) {
    const result = {};
    if (options.db) {
        result.db = options.db;
    }
    if (options.exportPath) {
        result.exportPath = options.exportPath;
    }
    return result;
}
