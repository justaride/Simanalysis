import assert from 'node:assert/strict';
import test from 'node:test';

import { patchDayOptions } from './patchDayApiModel.js';

test('patch day options omit empty state paths', () => {
    assert.deepEqual(patchDayOptions(), {});
    assert.deepEqual(patchDayOptions({ state: '   ' }), {});
});

test('patch day options include explicit state path', () => {
    assert.deepEqual(
        patchDayOptions({
            state: '/Sims/patch-day-state.json',
        }),
        {
            state: '/Sims/patch-day-state.json',
        },
    );
});
