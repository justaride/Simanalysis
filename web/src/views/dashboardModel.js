const SEVERITIES = ['critical', 'high', 'medium', 'low'];

function finiteNumber(value) {
    return Number.isFinite(value) ? value : 0;
}

function modExtension(mod) {
    if (mod?.type === 'package') return '.package';
    if (mod?.type === 'script') return '.ts4script';

    const raw = String(mod?.path || mod?.name || '').split(/[\\/]/).pop() || '';
    const match = raw.match(/(\.[^.]+)$/);
    return match ? match[1].toLowerCase() : 'other';
}

export function severityCounts(conflicts = []) {
    const rows = Array.isArray(conflicts) ? conflicts : [];
    return SEVERITIES.reduce((counts, severity) => {
        counts[severity] = rows.filter((conflict) => conflict?.severity === severity).length;
        return counts;
    }, {});
}

export function fileTypeDistribution(scanResult = {}) {
    const mods = Array.isArray(scanResult.mods) ? scanResult.mods : [];
    const counts = new Map();

    for (const mod of mods) {
        const key = modExtension(mod);
        counts.set(key, (counts.get(key) || 0) + 1);
    }

    return Array.from(counts.entries())
        .map(([name, value]) => ({ name, value }))
        .sort((left, right) => {
            const packageFirst = { '.package': 0, '.ts4script': 1 };
            const leftRank = packageFirst[left.name] ?? 2;
            const rightRank = packageFirst[right.name] ?? 2;
            if (leftRank !== rightRank) return leftRank - rightRank;
            return left.name.localeCompare(right.name);
        });
}

export function formatDashboardBytes(bytes) {
    const value = finiteNumber(bytes);
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function dashboardStats(scanResult = {}) {
    const mods = Array.isArray(scanResult.mods) ? scanResult.mods : [];
    const counts = severityCounts(scanResult.conflicts);
    const totalSizeBytes = mods.reduce((total, mod) => total + finiteNumber(mod?.size), 0);
    const totalFiles = finiteNumber(scanResult.summary?.total_mods) || mods.length;
    const healthScore = Math.max(
        0,
        100 - (counts.critical * 10) - (counts.high * 5) - (counts.medium * 2),
    );

    return {
        totalFiles,
        totalSizeBytes,
        totalSizeLabel: formatDashboardBytes(totalSizeBytes),
        severityCounts: counts,
        fileTypes: fileTypeDistribution(scanResult),
        healthScore,
    };
}
