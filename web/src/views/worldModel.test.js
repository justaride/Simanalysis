import test from 'node:test';
import assert from 'node:assert/strict';
import { groupUnitsByStatus, summarizeWorld } from './worldModel.js';

test('summarizeWorld extracts stable dashboard counts', () => {
    const summary = summarizeWorld({
        summary: {
            active_units: 2,
            disabled_units: 1,
            quarantined_units: 1,
            archived_units: 3,
            package_files: 8,
            script_files: 2,
            tray_files: 4,
            save_files: 5,
            log_files: 6,
            cache_files: 1,
            warnings: 0,
        },
    });

    assert.deepEqual(summary, {
        activeUnits: 2,
        disabledUnits: 1,
        quarantinedUnits: 1,
        archivedUnits: 3,
        packageFiles: 8,
        scriptFiles: 2,
        trayFiles: 4,
        saveFiles: 5,
        logFiles: 6,
        cacheFiles: 1,
        warnings: 0,
    });
});

test('summarizeWorld handles the empty initial page state', () => {
    assert.deepEqual(summarizeWorld(null), {
        activeUnits: 0,
        disabledUnits: 0,
        quarantinedUnits: 0,
        archivedUnits: 0,
        packageFiles: 0,
        scriptFiles: 0,
        trayFiles: 0,
        saveFiles: 0,
        logFiles: 0,
        cacheFiles: 0,
        warnings: 0,
    });
});

test('groupUnitsByStatus preserves unknown status without hiding units', () => {
    const grouped = groupUnitsByStatus([
        { name: 'A', status: 'active' },
        { name: 'D', status: 'disabled' },
        { name: 'Q', status: 'quarantined' },
        { name: 'X', status: 'unexpected' },
    ]);

    assert.deepEqual(Object.keys(grouped), [
        'active',
        'disabled',
        'quarantined',
        'archived',
        'unknown',
    ]);
    assert.equal(grouped.active.length, 1);
    assert.equal(grouped.unknown[0].name, 'X');
});
