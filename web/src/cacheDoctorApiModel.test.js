import assert from 'node:assert/strict';
import test from 'node:test';

import { cacheDoctorOptions } from './cacheDoctorApiModel.js';

test('cache doctor options are intentionally empty for read-only status', () => {
    assert.deepEqual(cacheDoctorOptions(), {});
    assert.deepEqual(cacheDoctorOptions({ ignored: true }), {});
});
