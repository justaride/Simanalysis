import assert from 'node:assert/strict';
import test from 'node:test';

import { doctorScanOptions } from './doctorApiModel.js';

test('doctor scan options keep existing defaults', () => {
    assert.deepEqual(doctorScanOptions('/Sims/Mods'), {
        modsPath: '/Sims/Mods',
        recursive: false,
    });
});

test('doctor scan options include explicit inventory database', () => {
    assert.deepEqual(
        doctorScanOptions('/Sims/Mods', {
            inventoryDb: '/Sims/inventory.sqlite3',
        }),
        {
            modsPath: '/Sims/Mods',
            recursive: false,
            inventoryDb: '/Sims/inventory.sqlite3',
        },
    );
});

test('doctor scan options include recursive only when requested', () => {
    assert.deepEqual(doctorScanOptions('/Sims/Mods', { recursive: true }), {
        modsPath: '/Sims/Mods',
        recursive: true,
    });

    assert.deepEqual(doctorScanOptions('/Sims/Mods', { recursive: false }), {
        modsPath: '/Sims/Mods',
        recursive: false,
    });
});

test('doctor scan options omit empty optional paths', () => {
    assert.deepEqual(
        doctorScanOptions('', {
            inventoryDb: '   ',
        }),
        { recursive: false },
    );
});
