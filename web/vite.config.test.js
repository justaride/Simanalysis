import test from 'node:test';
import assert from 'node:assert/strict';
import config from './vite.config.js';

const manualChunks = config.build.rollupOptions.output.manualChunks;

test('manual chunk config uses the function shape required by Vite 8', () => {
    assert.equal(typeof manualChunks, 'function');
});

test('manual chunk config keeps major libraries in stable bundles', () => {
    assert.equal(manualChunks('/project/node_modules/react/index.js'), 'vendor');
    assert.equal(manualChunks('/project/node_modules/react-dom/client.js'), 'vendor');
    assert.equal(manualChunks('/project/node_modules/recharts/es6/index.js'), 'charts');
    assert.equal(manualChunks('/project/node_modules/framer-motion/dist/es/index.mjs'), 'animations');
    assert.equal(manualChunks('/project/node_modules/@headlessui/react/dist/index.js'), 'ui');
    assert.equal(manualChunks('/project/src/views/Dashboard.jsx'), undefined);
});
