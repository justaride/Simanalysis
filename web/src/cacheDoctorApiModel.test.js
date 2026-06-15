import assert from 'node:assert/strict';
import test from 'node:test';

import {
    cacheCleanupApplyOptions,
    cacheCleanupPlanOptions,
    cacheCleanupRestoreOptions,
    cacheDoctorOptions,
    cacheOperationStatusOptions,
} from './cacheDoctorApiModel.js';

test('cache doctor options are intentionally empty for read-only status', () => {
    assert.deepEqual(cacheDoctorOptions(), {});
    assert.deepEqual(cacheDoctorOptions({ ignored: true }), {});
});

test('cache cleanup plan options require explicit export path', () => {
    assert.throws(() => cacheCleanupPlanOptions(), /requires exportPath/);
    assert.deepEqual(
        cacheCleanupPlanOptions({ exportPath: ' /tmp/cache-plan.json ' }),
        { exportPath: '/tmp/cache-plan.json' },
    );
});

test('cache cleanup apply options include selected actions', () => {
    assert.deepEqual(
        cacheCleanupApplyOptions({
            actions: ['cache-clear-001', '', ' cache-clear-002 '],
        }),
        { actions: ['cache-clear-001', 'cache-clear-002'], allActions: false },
    );
});

test('cache cleanup apply options include all-actions gate', () => {
    assert.deepEqual(
        cacheCleanupApplyOptions({ allActions: true }),
        { actions: [], allActions: true },
    );
});

test('cache cleanup apply options reject ambiguous or empty selection', () => {
    assert.throws(
        () => cacheCleanupApplyOptions({ actions: ['cache-clear-001'], allActions: true }),
        /Choose actions or allActions/,
    );
    assert.throws(() => cacheCleanupApplyOptions(), /requires at least one action/);
});

test('cache cleanup restore and operation status options are empty', () => {
    assert.deepEqual(cacheCleanupRestoreOptions(), {});
    assert.deepEqual(cacheOperationStatusOptions(), {});
});
