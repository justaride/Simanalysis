export function inventoryScanOptions(options = {}) {
    const result = { export: true };
    if (options.db) {
        result.db = options.db;
    }
    return result;
}

export function inventoryHistoryOptions(options = {}) {
    const limit = options.limit ?? 10;
    if (!Number.isInteger(limit)) {
        throw new Error('Inventory history limit must be a whole number');
    }
    if (limit <= 0) {
        throw new Error('Inventory history limit must be greater than zero');
    }

    const result = { limit };
    if (options.db) {
        result.db = options.db;
    }
    return result;
}
