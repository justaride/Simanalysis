import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupStageOptions } from './operatingTableApiModel.js';

test('cleanup stage options require a plan path', () => {
    assert.throws(
        () => cleanupStageOptions({ actions: ['duplicate:1'] }),
        /planPath/,
    );
});

test('cleanup stage options include selected actions', () => {
    assert.deepEqual(
        cleanupStageOptions({
            planPath: '/tmp/cleanup-plan.json',
            actions: ['duplicate:1', 'archive:1'],
        }),
        {
            planPath: '/tmp/cleanup-plan.json',
            actions: ['duplicate:1', 'archive:1'],
            allActions: false,
        },
    );
});

test('cleanup stage options include all-actions flag', () => {
    assert.deepEqual(
        cleanupStageOptions({
            planPath: '/tmp/cleanup-plan.json',
            allActions: true,
        }),
        {
            planPath: '/tmp/cleanup-plan.json',
            actions: [],
            allActions: true,
        },
    );
});

test('cleanup stage options reject action and all-actions together', () => {
    assert.throws(
        () => cleanupStageOptions({
            planPath: '/tmp/cleanup-plan.json',
            actions: ['duplicate:1'],
            allActions: true,
        }),
        /either selected actions or allActions/,
    );
});
