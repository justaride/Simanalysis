import assert from 'node:assert/strict';
import test from 'node:test';

import { hasTauriInvoke } from './tauriRuntime.js';

test('tauri invoke detection is false outside Tauri', () => {
    assert.equal(hasTauriInvoke({}), false);
    assert.equal(hasTauriInvoke({ __TAURI_INTERNALS__: {} }), false);
    assert.equal(hasTauriInvoke(null), false);
});

test('tauri invoke detection is true when the runtime exposes invoke', () => {
    assert.equal(
        hasTauriInvoke({
            __TAURI_INTERNALS__: {
                invoke: () => {},
            },
        }),
        true,
    );
});
