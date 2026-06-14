import test from 'node:test';
import assert from 'node:assert/strict';

import { cleanupPlanOptions } from './cleanupApiModel.js';

test('cleanup plan options are empty by default', () => {
    assert.deepEqual(cleanupPlanOptions(), {});
});

test('cleanup plan includes explicit database and export paths', () => {
    assert.deepEqual(
        cleanupPlanOptions({
            db: '/tmp/inventory.sqlite3',
            exportPath: '/tmp/cleanup-plan.json',
        }),
        {
            db: '/tmp/inventory.sqlite3',
            exportPath: '/tmp/cleanup-plan.json',
        },
    );
});
