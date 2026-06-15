import assert from 'node:assert/strict';
import test from 'node:test';

import { updateDeskOptions } from './updateDeskApiModel.js';

test('update desk options are intentionally empty for read-only staging status', () => {
    assert.deepEqual(updateDeskOptions(), {});
    assert.deepEqual(updateDeskOptions({ ignored: true }), {});
});
