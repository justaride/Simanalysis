import test from 'node:test';
import assert from 'node:assert/strict';

import {
    inventoryFileEventsOptions,
    inventoryHistoryOptions,
    inventoryScanOptions,
} from './inventoryApiModel.js';

test('inventory scan requests snapshot export by default', () => {
    assert.deepEqual(inventoryScanOptions(), { export: true });
});

test('inventory scan includes explicit database path when provided', () => {
    assert.deepEqual(inventoryScanOptions({ db: '/tmp/inventory.sqlite3' }), {
        db: '/tmp/inventory.sqlite3',
        export: true,
    });
});

test('inventory history defaults to a bounded recent scan list', () => {
    assert.deepEqual(inventoryHistoryOptions(), { limit: 10 });
});

test('inventory history validates positive integer limits', () => {
    assert.throws(() => inventoryHistoryOptions({ limit: 0 }), /greater than zero/);
    assert.throws(() => inventoryHistoryOptions({ limit: 1.5 }), /whole number/);
});

test('inventory file events omit unchanged files by default', () => {
    assert.deepEqual(inventoryFileEventsOptions(), {});
});

test('inventory file events can include unchanged files and explicit database path', () => {
    assert.deepEqual(
        inventoryFileEventsOptions({
            db: '/tmp/inventory.sqlite3',
            includeUnchanged: true,
        }),
        {
            db: '/tmp/inventory.sqlite3',
            includeUnchanged: true,
        },
    );
});
