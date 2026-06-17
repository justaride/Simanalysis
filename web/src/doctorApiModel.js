function optionalTrimmedPath(value) {
    const path = String(value || '').trim();
    return path || null;
}

export function doctorScanOptions(modsPath, options = {}) {
    const result = { recursive: options.recursive === true };
    const mods = optionalTrimmedPath(modsPath);
    const inventoryDb = optionalTrimmedPath(options.inventoryDb);

    if (mods) {
        result.modsPath = mods;
    }
    if (inventoryDb) {
        result.inventoryDb = inventoryDb;
    }

    return result;
}
