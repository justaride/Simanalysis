export function summarizeWorld(data = {}) {
    const summary = data?.summary || {};
    return {
        activeUnits: summary.active_units || 0,
        disabledUnits: summary.disabled_units || 0,
        quarantinedUnits: summary.quarantined_units || 0,
        archivedUnits: summary.archived_units || 0,
        packageFiles: summary.package_files || 0,
        scriptFiles: summary.script_files || 0,
        trayFiles: summary.tray_files || 0,
        saveFiles: summary.save_files || 0,
        logFiles: summary.log_files || 0,
        cacheFiles: summary.cache_files || 0,
        warnings: summary.warnings || 0,
    };
}

export function groupUnitsByStatus(units = []) {
    const grouped = {
        active: [],
        disabled: [],
        quarantined: [],
        archived: [],
        unknown: [],
    };

    units.forEach((unit) => {
        if (grouped[unit.status]) {
            grouped[unit.status].push(unit);
            return;
        }
        grouped.unknown.push(unit);
    });

    return grouped;
}

export function formatBytes(bytes = 0) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let index = 0;
    while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index += 1;
    }
    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
