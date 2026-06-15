import assert from 'node:assert/strict';
import test from 'node:test';

import {
    updateDeskCommitOptions,
    updateDeskOptions,
    updateDeskPlanOptions,
    updateDeskUndoOptions,
} from './updateDeskApiModel.js';

test('update desk options are intentionally empty for read-only staging status', () => {
    assert.deepEqual(updateDeskOptions(), {});
    assert.deepEqual(updateDeskOptions({ ignored: true }), {});
});

test('update desk plan options require an explicit Mods path', () => {
    assert.deepEqual(updateDeskPlanOptions('/Sims/The Sims 4/Mods'), {
        modsPath: '/Sims/The Sims 4/Mods',
    });
    assert.deepEqual(updateDeskPlanOptions('  /Sims/The Sims 4/Mods  '), {
        modsPath: '/Sims/The Sims 4/Mods',
    });
    assert.throws(() => updateDeskPlanOptions(''), /modsPath/);
    assert.throws(() => updateDeskPlanOptions(null), /modsPath/);
});

test('update desk commit options require explicit actions or all-actions', () => {
    assert.deepEqual(updateDeskCommitOptions({ actions: [' update-copy-001 ', 'update-copy-002'] }), {
        actions: ['update-copy-001', 'update-copy-002'],
        allActions: false,
    });
    assert.deepEqual(updateDeskCommitOptions({ allActions: true }), {
        actions: [],
        allActions: true,
    });
    assert.throws(() => updateDeskCommitOptions(), /action/);
    assert.throws(() => updateDeskCommitOptions({ actions: [] }), /action/);
    assert.throws(
        () => updateDeskCommitOptions({ actions: ['update-copy-001'], allActions: true }),
        /Choose actions or allActions/,
    );
});

test('update desk undo options are intentionally empty', () => {
    assert.deepEqual(updateDeskUndoOptions(), {});
});
