import assert from 'node:assert/strict';
import test from 'node:test';

import {
    canApplyCachePlan,
    getEligibleCacheActionRows,
    selectAllCacheActions,
    summarizeCacheCleanupPlan,
    summarizeCacheOperation,
    summarizeCacheStatus,
    toCachePlanActionRows,
    toCacheTargetRows,
    toggleCacheActionSelection,
} from './cacheDoctorModel.js';

const CACHE_PAYLOAD = {
    status: 'review_recommended',
    root_path: '/Sims/The Sims 4',
    present_count: 2,
    total_size_bytes: 1536,
    mutates_files: false,
    warnings: ['Skipped symlinked cache target: /Sims/The Sims 4/cache'],
    recommendations: ['Review listed cache targets before deleting anything.'],
    targets: [
        {
            id: 'avatarcache',
            label: 'Avatar cache',
            relative_path: 'avatarcache.package',
            kind: 'file',
            risk: 'low',
            reason: 'Can retain stale Sim portrait data.',
            present: false,
            status: 'absent',
            size_bytes: 0,
            item_count: 0,
            modified_at: null,
        },
        {
            id: 'localthumbcache',
            label: 'Local thumbnail cache',
            relative_path: 'localthumbcache.package',
            kind: 'file',
            risk: 'medium',
            reason: 'Can retain stale thumbnails.',
            present: true,
            status: 'present',
            size_bytes: 1536,
            item_count: 1,
            modified_at: '2026-06-15T04:00:00Z',
        },
    ],
};

const CACHE_PLAN = {
    status: 'ready_for_review',
    plan_id: 'cache-plan-20260615T100000',
    generated_at: '2026-06-15T10:00:00Z',
    root_path: '/Sims/The Sims 4',
    manifest_path: '/tmp/cache-plan.json',
    action_count: 2,
    blocked_count: 1,
    requires_snapshot: true,
    mutates_files: false,
    warnings: ['Skipped symlinked cache target'],
    recommendations: ['Close The Sims 4 before applying.'],
    actions: [
        {
            action_id: 'cache-clear-001',
            action_type: 'quarantine_cache_target',
            target_id: 'localthumbcache',
            label: 'Local thumbnail cache',
            status: 'planned',
            source_relative_path: 'localthumbcache.package',
            quarantine_relative_path: '_Simanalysis_CacheDoctor/quarantine/pending/localthumbcache.package',
            expected: { size: 1536, item_count: 1 },
            risk: 'medium',
            blockers: [],
        },
        {
            action_id: 'cache-clear-002',
            action_type: 'quarantine_cache_target',
            target_id: 'cache_dir',
            label: 'Cache directory',
            status: 'blocked',
            source_relative_path: 'cache',
            quarantine_relative_path: '_Simanalysis_CacheDoctor/quarantine/pending/cache',
            expected: { size: 0, item_count: 0 },
            risk: 'medium',
            blockers: ['cache_target_symlink'],
        },
    ],
};

const CACHE_OPERATION = {
    operation_id: 'cache-op-20260615-100000',
    status: 'applied',
    manifest_path: '/Sims/The Sims 4/_Simanalysis_CacheDoctor/manifests/cache-op.json',
    actions: [
        { action_id: 'cache-clear-001', status: 'quarantined' },
        { action_id: 'cache-clear-002', status: 'blocked' },
    ],
};

test('cache doctor summary preserves read-only status and counts', () => {
    assert.deepEqual(summarizeCacheStatus(CACHE_PAYLOAD), {
        status: 'review_recommended',
        statusLabel: 'Review recommended',
        tone: 'amber',
        rootPath: '/Sims/The Sims 4',
        presentCount: 2,
        totalSizeBytes: 1536,
        totalSizeLabel: '1.5 KB',
        warningCount: 1,
        recommendationCount: 1,
        readOnlyLabel: 'Read-only',
    });
});

test('cache target rows sort present targets first and keep absent targets visible', () => {
    assert.deepEqual(toCacheTargetRows(CACHE_PAYLOAD), [
        {
            id: 'localthumbcache',
            label: 'Local thumbnail cache',
            relativePath: 'localthumbcache.package',
            kindLabel: 'File',
            riskLabel: 'Medium',
            reason: 'Can retain stale thumbnails.',
            present: true,
            status: 'present',
            statusLabel: 'Present',
            sizeBytes: 1536,
            sizeLabel: '1.5 KB',
            itemCount: 1,
            modifiedAt: '2026-06-15T04:00:00Z',
        },
        {
            id: 'avatarcache',
            label: 'Avatar cache',
            relativePath: 'avatarcache.package',
            kindLabel: 'File',
            riskLabel: 'Low',
            reason: 'Can retain stale Sim portrait data.',
            present: false,
            status: 'absent',
            statusLabel: 'Absent',
            sizeBytes: 0,
            sizeLabel: '0 B',
            itemCount: 0,
            modifiedAt: null,
        },
    ]);
});

test('cache doctor summary falls back without inventing mutation support', () => {
    assert.equal(summarizeCacheStatus({}).readOnlyLabel, 'Read-only');
    assert.equal(summarizeCacheStatus({ mutates_files: true }).readOnlyLabel, 'Mutation reported');
    assert.deepEqual(toCacheTargetRows({}), []);
});

test('cache cleanup plan summary preserves safety gates', () => {
    assert.deepEqual(summarizeCacheCleanupPlan(CACHE_PLAN), {
        status: 'ready_for_review',
        statusLabel: 'Ready for review',
        tone: 'green',
        planId: 'cache-plan-20260615T100000',
        generatedAt: '2026-06-15T10:00:00Z',
        rootPath: '/Sims/The Sims 4',
        manifestPath: '/tmp/cache-plan.json',
        actionCount: 2,
        blockedCount: 1,
        warningCount: 1,
        recommendationCount: 1,
        requiresSnapshotLabel: 'Snapshot required',
        readOnlyLabel: 'Read-only',
    });
});

test('cache cleanup plan action rows expose quarantine targets and blockers', () => {
    assert.deepEqual(toCachePlanActionRows(CACHE_PLAN), [
        {
            id: 'cache-clear-001',
            type: 'quarantine_cache_target',
            typeLabel: 'Quarantine Cache Target',
            targetId: 'localthumbcache',
            label: 'Local thumbnail cache',
            status: 'planned',
            statusLabel: 'Planned',
            sourceRelativePath: 'localthumbcache.package',
            quarantineRelativePath: '_Simanalysis_CacheDoctor/quarantine/pending/localthumbcache.package',
            expectedSizeLabel: '1.5 KB',
            expectedItemCount: 1,
            riskLabel: 'Medium',
            blockers: [],
        },
        {
            id: 'cache-clear-002',
            type: 'quarantine_cache_target',
            typeLabel: 'Quarantine Cache Target',
            targetId: 'cache_dir',
            label: 'Cache directory',
            status: 'blocked',
            statusLabel: 'Blocked',
            sourceRelativePath: 'cache',
            quarantineRelativePath: '_Simanalysis_CacheDoctor/quarantine/pending/cache',
            expectedSizeLabel: '0 B',
            expectedItemCount: 0,
            riskLabel: 'Medium',
            blockers: ['cache_target_symlink'],
        },
    ]);
});

test('cache action selection is stable and eligible-only', () => {
    const rows = toCachePlanActionRows(CACHE_PLAN);
    assert.deepEqual(getEligibleCacheActionRows(rows).map((row) => row.id), ['cache-clear-001']);
    assert.deepEqual(selectAllCacheActions(rows), ['cache-clear-001']);
    assert.deepEqual(toggleCacheActionSelection([], 'cache-clear-001', true), ['cache-clear-001']);
    assert.deepEqual(
        toggleCacheActionSelection(['cache-clear-001'], 'cache-clear-001', true),
        ['cache-clear-001'],
    );
    assert.deepEqual(toggleCacheActionSelection(['cache-clear-001'], 'cache-clear-001', false), []);
});

test('cache apply gate requires plan path and explicit eligible selection', () => {
    assert.equal(
        canApplyCachePlan({
            planPath: '/tmp/cache-plan.json',
            selectedActionIds: ['cache-clear-001'],
            eligibleActionCount: 1,
        }),
        true,
    );
    assert.equal(canApplyCachePlan({ planPath: '', selectedActionIds: ['cache-clear-001'], eligibleActionCount: 1 }), false);
    assert.equal(canApplyCachePlan({ planPath: '/tmp/cache-plan.json', selectedActionIds: [], eligibleActionCount: 1 }), false);
    assert.equal(canApplyCachePlan({ planPath: '/tmp/cache-plan.json', selectedActionIds: ['cache-clear-001'], eligibleActionCount: 0 }), false);
});

test('cache operation summary supports restore after quarantine', () => {
    assert.deepEqual(summarizeCacheOperation(CACHE_OPERATION), {
        operationId: 'cache-op-20260615-100000',
        status: 'applied',
        statusLabel: 'Applied',
        tone: 'green',
        manifestPath: '/Sims/The Sims 4/_Simanalysis_CacheDoctor/manifests/cache-op.json',
        quarantinedCount: 1,
        restoredCount: 0,
        blockedCount: 1,
        canRestore: true,
    });
    assert.equal(summarizeCacheOperation({ status: 'restored', actions: [{ status: 'restored' }] }).canRestore, false);
});
