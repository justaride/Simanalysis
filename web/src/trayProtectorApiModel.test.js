import assert from 'node:assert/strict';
import test from 'node:test';

import { trayProtectorOptions } from './trayProtectorApiModel.js';

test('tray protector options are intentionally empty for read-only status', () => {
    assert.deepEqual(trayProtectorOptions(), {});
    assert.deepEqual(trayProtectorOptions({ ignored: true }), {});
});
