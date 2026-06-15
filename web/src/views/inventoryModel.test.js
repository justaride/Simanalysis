import assert from 'node:assert/strict';
import test from 'node:test';

import {
    changeStatusLabel,
    fileKindLabel,
    formatInventoryBytes,
    latestHistoryScan,
    summarizeInventoryScan,
    toInventoryEventRows,
    toInventoryFileRows,
} from './inventoryModel.js';

const SCAN_PAYLOAD = {
    scan_id: 42,
    root_path: '/Sims/The Sims 4',
    db_path: '/Users/me/Library/Application Support/Simanalysis/inventory.sqlite3',
    files_total: 5,
    packages_total: 2,
    resources_total: 17,
    package_parse_errors: 1,
    added: 2,
    removed: 1,
    moved: 1,
    modified: 1,
    unchanged: 0,
    warnings: ['Skipped symlinked path: Mods/link'],
    snapshot: {
        created_at: '2026-06-15T12:00:00+00:00',
        files: [
            {
                relative_path: 'Mods/a.package',
                extension: '.package',
                size: 2048,
                sha256: 'aaa',
                change_status: 'added',
                package: {
                    parse_status: 'ok',
                    parse_error: null,
                    resource_count: 12,
                },
            },
            {
                relative_path: 'Mods/b.ts4script',
                extension: '.ts4script',
                size: 1536,
                sha256: 'bbb',
                change_status: 'moved',
                package: null,
            },
            {
                relative_path: 'Options.ini',
                extension: '.ini',
                size: 256,
                sha256: 'ccc',
                change_status: 'modified',
                package: null,
            },
        ],
    },
};

test('inventory scan summary preserves ledger counts and paths', () => {
    assert.deepEqual(summarizeInventoryScan(SCAN_PAYLOAD), {
        scanId: 42,
        rootPath: '/Sims/The Sims 4',
        dbPath: '/Users/me/Library/Application Support/Simanalysis/inventory.sqlite3',
        filesTotal: 5,
        packagesTotal: 2,
        resourcesTotal: 17,
        packageParseErrors: 1,
        added: 2,
        removed: 1,
        moved: 1,
        modified: 1,
        unchanged: 0,
        changedTotal: 5,
        snapshotCreatedAt: '2026-06-15T12:00:00+00:00',
        warnings: ['Skipped symlinked path: Mods/link'],
    });
});

test('inventory summary falls back without inventing ledger data', () => {
    assert.deepEqual(summarizeInventoryScan({}), {
        scanId: null,
        rootPath: null,
        dbPath: null,
        filesTotal: 0,
        packagesTotal: 0,
        resourcesTotal: 0,
        packageParseErrors: 0,
        added: 0,
        removed: 0,
        moved: 0,
        modified: 0,
        unchanged: 0,
        changedTotal: 0,
        snapshotCreatedAt: null,
        warnings: [],
    });
});

test('inventory file rows are sorted, labeled, and compact', () => {
    assert.deepEqual(toInventoryFileRows(SCAN_PAYLOAD), [
        {
            relativePath: 'Mods/a.package',
            extension: '.package',
            kindLabel: 'Package',
            sizeBytes: 2048,
            sizeLabel: '2 KB',
            changeStatus: 'added',
            changeLabel: 'Added',
            packageStatus: 'ok',
            packageLabel: 'Parsed',
            resourceCount: 12,
            sha256: 'aaa',
        },
        {
            relativePath: 'Mods/b.ts4script',
            extension: '.ts4script',
            kindLabel: 'Script',
            sizeBytes: 1536,
            sizeLabel: '1.5 KB',
            changeStatus: 'moved',
            changeLabel: 'Moved',
            packageStatus: null,
            packageLabel: 'Not a package',
            resourceCount: null,
            sha256: 'bbb',
        },
        {
            relativePath: 'Options.ini',
            extension: '.ini',
            kindLabel: 'INI',
            sizeBytes: 256,
            sizeLabel: '256 B',
            changeStatus: 'modified',
            changeLabel: 'Modified',
            packageStatus: null,
            packageLabel: 'Not a package',
            resourceCount: null,
            sha256: 'ccc',
        },
    ]);
});

test('inventory history picks the newest scan conservatively', () => {
    assert.deepEqual(
        latestHistoryScan({
            scans: [
                { scan_id: 8, files_total: 10, added: 0 },
                { scan_id: 7, files_total: 9, added: 1 },
            ],
        }),
        { scan_id: 8, files_total: 10, added: 0 },
    );
    assert.equal(latestHistoryScan({ scans: [] }), null);
    assert.equal(latestHistoryScan({}), null);
});

test('inventory event rows preserve move source context', () => {
    assert.deepEqual(
        toInventoryEventRows({
            events: [
                {
                    relative_path: 'Mods/new.package',
                    previous_relative_path: 'Mods/old.package',
                    change_status: 'moved',
                    size: 1024,
                    sha256: 'ddd',
                },
                {
                    relative_path: 'Mods/old.package',
                    previous_relative_path: 'Mods/new.package',
                    change_status: 'moved_source',
                    size: 1024,
                    sha256: 'ddd',
                },
            ],
        }),
        [
            {
                relativePath: 'Mods/new.package',
                previousRelativePath: 'Mods/old.package',
                changeStatus: 'moved',
                changeLabel: 'Moved',
                sizeBytes: 1024,
                sizeLabel: '1 KB',
                sha256: 'ddd',
            },
            {
                relativePath: 'Mods/old.package',
                previousRelativePath: 'Mods/new.package',
                changeStatus: 'moved_source',
                changeLabel: 'Moved source',
                sizeBytes: 1024,
                sizeLabel: '1 KB',
                sha256: 'ddd',
            },
        ],
    );
});

test('inventory labels keep unknown values visible', () => {
    assert.equal(changeStatusLabel('moved_source'), 'Moved source');
    assert.equal(changeStatusLabel('future_status'), 'future status');
    assert.equal(fileKindLabel('.package'), 'Package');
    assert.equal(fileKindLabel('.ts4script'), 'Script');
    assert.equal(fileKindLabel('.weird'), 'WEIRD');
    assert.equal(fileKindLabel(''), 'File');
});

test('inventory byte formatting is stable for scan totals', () => {
    assert.equal(formatInventoryBytes(0), '0 B');
    assert.equal(formatInventoryBytes(512), '512 B');
    assert.equal(formatInventoryBytes(1536), '1.5 KB');
    assert.equal(formatInventoryBytes(1048576), '1 MB');
    assert.equal(formatInventoryBytes(null), '0 B');
});
