import assert from 'node:assert/strict';
import test from 'node:test';

import { updateDeskOptions, updateDeskPlanOptions } from './updateDeskApiModel.js';

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
