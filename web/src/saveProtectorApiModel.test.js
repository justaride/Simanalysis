import assert from 'node:assert/strict';
import test from 'node:test';

import { saveProtectorOptions } from './saveProtectorApiModel.js';

test('save protector options are intentionally empty for read-only status', () => {
    assert.deepEqual(saveProtectorOptions(), {});
    assert.deepEqual(saveProtectorOptions({ ignored: true }), {});
});
