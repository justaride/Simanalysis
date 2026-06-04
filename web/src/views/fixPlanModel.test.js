import test from 'node:test';
import assert from 'node:assert/strict';
import {
    getFixActionAffordance,
    groupActionsBySeverity,
    summarizeFixPlan,
    summarizeFixSession,
} from './fixPlanModel.js';

test('summarizeFixPlan handles empty initial state', () => {
    assert.deepEqual(summarizeFixPlan(null), {
        actions: 0,
        high: 0,
        medium: 0,
        low: 0,
        warnings: 0,
        blockers: 0,
    });
});

test('groupActionsBySeverity keeps unknown severities visible', () => {
    const grouped = groupActionsBySeverity([
        { title: 'A', severity: 'high' },
        { title: 'B', severity: 'medium' },
        { title: 'C', severity: 'low' },
        { title: 'D', severity: 'later' },
    ]);

    assert.deepEqual(Object.keys(grouped), ['high', 'medium', 'low', 'unknown']);
    assert.equal(grouped.high[0].title, 'A');
    assert.equal(grouped.unknown[0].title, 'D');
});

test('getFixActionAffordance exposes only manifest-backed cache cleanup as applyable', () => {
    const applyable = getFixActionAffordance({
        kind: 'cache_cleanup_candidate',
        can_apply: true,
        proposed_operation: 'move_to_simanalysis_cache_backup',
    });
    const reviewOnly = getFixActionAffordance({
        kind: 'duplicate_mod_candidate',
        can_apply: false,
        proposed_operation: 'review',
    });

    assert.deepEqual(applyable, {
        actionKind: 'cache_cleanup',
        badge: 'Manifest-backed',
        label: 'Move Cache to Backup',
        tone: 'emerald',
    });
    assert.deepEqual(reviewOnly, {
        actionKind: null,
        badge: 'Review-only',
        label: null,
        tone: 'cyan',
    });
});

test('summarizeFixSession derives restore state from manifest session', () => {
    assert.deepEqual(summarizeFixSession(null), {
        canRestore: false,
        manifestPath: null,
        recordCount: 0,
        status: 'none',
    });

    assert.deepEqual(
        summarizeFixSession({
            status: 'applied',
            manifest_path: '/tmp/session.json',
            records: [{ status: 'moved' }],
        }),
        {
            canRestore: true,
            manifestPath: '/tmp/session.json',
            recordCount: 1,
            status: 'applied',
        },
    );

    assert.equal(
        summarizeFixSession({
            status: 'restored',
            manifest_path: '/tmp/session.json',
            records: [{ status: 'restored' }],
        }).canRestore,
        false,
    );
});
