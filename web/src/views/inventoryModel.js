const CHANGE_LABELS = {
    added: 'Added',
    removed: 'Removed',
    moved: 'Moved',
    moved_source: 'Moved source',
    modified: 'Modified',
    unchanged: 'Unchanged',
};

const FILE_KIND_LABELS = {
    '.package': 'Package',
    '.ts4script': 'Script',
};

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

function words(value) {
    return String(value || 'unknown').replaceAll('_', ' ');
}

export function changeStatusLabel(status) {
    return CHANGE_LABELS[status] || words(status);
}

export function fileKindLabel(extension) {
    if (!extension) return 'File';
    return FILE_KIND_LABELS[extension] || extension.replace(/^\./, '').toUpperCase();
}

export function formatInventoryBytes(bytes) {
    const value = Number.isFinite(bytes) ? bytes : 0;
    if (value === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const amount = value / (1024 ** index);
    const rounded = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1);
    return `${rounded} ${units[index]}`;
}

export function summarizeInventoryScan(payload = {}) {
    const snapshot = payload.snapshot || {};
    const added = count(payload.added);
    const removed = count(payload.removed);
    const moved = count(payload.moved);
    const modified = count(payload.modified);

    return {
        scanId: payload.scan_id ?? null,
        rootPath: payload.root_path || null,
        dbPath: payload.db_path || null,
        filesTotal: count(payload.files_total),
        packagesTotal: count(payload.packages_total),
        resourcesTotal: count(payload.resources_total),
        packageParseErrors: count(payload.package_parse_errors),
        added,
        removed,
        moved,
        modified,
        unchanged: count(payload.unchanged),
        changedTotal: added + removed + moved + modified,
        snapshotCreatedAt: snapshot.created_at || null,
        warnings: Array.isArray(payload.warnings) ? payload.warnings : [],
    };
}

export function toInventoryFileRows(payload = {}) {
    const files = Array.isArray(payload.snapshot?.files) ? payload.snapshot.files : [];
    return files.map((file) => {
        const packageInfo = file.package || null;
        const packageStatus = packageInfo?.parse_status || null;
        return {
            relativePath: file.relative_path || '',
            extension: file.extension || '',
            kindLabel: fileKindLabel(file.extension),
            sizeBytes: count(file.size),
            sizeLabel: formatInventoryBytes(file.size),
            changeStatus: file.change_status || 'unknown',
            changeLabel: changeStatusLabel(file.change_status),
            packageStatus,
            packageLabel: packageStatus === 'ok'
                ? 'Parsed'
                : packageStatus === 'error'
                  ? 'Parse warning'
                  : 'Not a package',
            resourceCount: Number.isFinite(packageInfo?.resource_count)
                ? packageInfo.resource_count
                : null,
            sha256: file.sha256 || '',
        };
    }).sort((left, right) => left.relativePath.localeCompare(right.relativePath));
}

export function toInventoryEventRows(payload = {}) {
    const events = Array.isArray(payload.events) ? payload.events : [];
    return events.map((event) => ({
        relativePath: event.relative_path || '',
        previousRelativePath: event.previous_relative_path || null,
        changeStatus: event.change_status || 'unknown',
        changeLabel: changeStatusLabel(event.change_status),
        sizeBytes: count(event.size),
        sizeLabel: formatInventoryBytes(event.size),
        sha256: event.sha256 || '',
    }));
}

export function latestHistoryScan(payload = {}) {
    const scans = Array.isArray(payload.scans) ? payload.scans : [];
    return scans[0] || null;
}
