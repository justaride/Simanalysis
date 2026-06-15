import assert from 'node:assert/strict';
import test from 'node:test';

import * as cleanupModel from './cleanupModel.js';

const {
    cleanupCategoryLabel,
    flattenCleanupActions,
    summarizeCleanupPlan,
} = cleanupModel;

const PLAN = {
    plan_id: 'cleanup-20260612-101400',
    root_path: '/Sims/The Sims 4',
    db_path: '/Sims/The Sims 4/_Simanalysis/inventory.sqlite3',
    warnings: ['Latest inventory snapshot contains no Mods files'],
    summary: {
        files_considered: 6,
        finding_count: 2,
        action_count: 3,
        duplicate_groups: 1,
        archives: 1,
        duplicate_resource_cfg: 0,
        support_files: 0,
        misplaced_tray: 0,
    },
    findings: [
        {
            finding_id: 'duplicate:sha256:abc',
            category: 'exact_duplicate',
            severity: 'review',
            title: 'Exact duplicate files',
            explanation: 'These files have identical SHA-256 and size in Mods.',
            evidence: {
                keep_candidate: 'Mods/A/item.package',
                paths: ['Mods/A/item.package', 'Mods/B/item.package'],
            },
            actions: [
                {
                    action_id: 'duplicate:1',
                    kind: 'review_duplicate',
                    source_relative_path: 'Mods/B/item.package',
                    proposed_destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/duplicates/Mods/B/item.package',
                    reason: 'Exact duplicate of Mods/A/item.package',
                },
            ],
        },
        {
            finding_id: 'inactive_archive:Mods/download.zip',
            category: 'inactive_archive',
            severity: 'review',
            title: 'Archive file inside Mods',
            explanation: 'The Sims 4 does not load this archive directly from Mods.',
            evidence: {
                path: 'Mods/download.zip',
                size: 128,
            },
            actions: [
                {
                    action_id: 'inactive_archive:1:Mods/download.zip',
                    kind: 'review_archive',
                    source_relative_path: 'Mods/download.zip',
                    proposed_destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/archives/Mods/download.zip',
                    reason: 'The Sims 4 does not load this archive directly from Mods.',
                },
                {
                    action_id: 'inactive_archive:1:Mods/old.rar',
                    kind: 'review_archive',
                    source_relative_path: 'Mods/old.rar',
                    proposed_destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/archives/Mods/old.rar',
                    reason: 'The Sims 4 does not load this archive directly from Mods.',
                },
            ],
        },
    ],
};

const MANIFEST = {
    operation_id: 'cleanup-op-20260612-101530',
    manifest_path: '/Sims/The Sims 4/_Simanalysis_Cleanup/manifests/cleanup-op-20260612-101530.json',
    status: 'partial',
    warnings: ['Manifest warning'],
    blockers: ['The Sims 4 is running'],
    actions: [
        {
            action_id: 'duplicate:1',
            status: 'moved',
            error: null,
        },
        {
            action_id: 'inactive_archive:1:Mods/download.zip',
            status: 'blocked',
            error: 'Hash changed before apply',
        },
        {
            action_id: 'support:1:Mods/readme.txt',
            status: 'pending',
            error: null,
        },
    ],
};

test('cleanup plan summary is stable and conservative', () => {
    assert.deepEqual(summarizeCleanupPlan(PLAN), {
        planId: 'cleanup-20260612-101400',
        rootPath: '/Sims/The Sims 4',
        dbPath: '/Sims/The Sims 4/_Simanalysis/inventory.sqlite3',
        filesConsidered: 6,
        findingCount: 2,
        actionCount: 3,
        duplicateGroups: 1,
        archives: 1,
        duplicateResourceCfg: 0,
        supportFiles: 0,
        misplacedTray: 0,
        warnings: ['Latest inventory snapshot contains no Mods files'],
    });
});

test('cleanup plan summary falls back without inventing counts', () => {
    assert.deepEqual(summarizeCleanupPlan({}), {
        planId: null,
        rootPath: null,
        dbPath: null,
        filesConsidered: 0,
        findingCount: 0,
        actionCount: 0,
        duplicateGroups: 0,
        archives: 0,
        duplicateResourceCfg: 0,
        supportFiles: 0,
        misplacedTray: 0,
        warnings: [],
    });
});

test('cleanup actions flatten with finding context and destinations', () => {
    assert.deepEqual(flattenCleanupActions(PLAN), [
        {
            id: 'duplicate:1',
            kind: 'review_duplicate',
            category: 'exact_duplicate',
            categoryLabel: 'Exact Duplicates',
            title: 'Exact duplicate files',
            severity: 'review',
            source: 'Mods/B/item.package',
            destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/duplicates/Mods/B/item.package',
            reason: 'Exact duplicate of Mods/A/item.package',
            keepCandidate: 'Mods/A/item.package',
        },
        {
            id: 'inactive_archive:1:Mods/download.zip',
            kind: 'review_archive',
            category: 'inactive_archive',
            categoryLabel: 'Archives',
            title: 'Archive file inside Mods',
            severity: 'review',
            source: 'Mods/download.zip',
            destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/archives/Mods/download.zip',
            reason: 'The Sims 4 does not load this archive directly from Mods.',
            keepCandidate: null,
        },
        {
            id: 'inactive_archive:1:Mods/old.rar',
            kind: 'review_archive',
            category: 'inactive_archive',
            categoryLabel: 'Archives',
            title: 'Archive file inside Mods',
            severity: 'review',
            source: 'Mods/old.rar',
            destination: '_Simanalysis_Cleanup/cleanup-20260612-101400/archives/Mods/old.rar',
            reason: 'The Sims 4 does not load this archive directly from Mods.',
            keepCandidate: null,
        },
    ]);
});

test('cleanup category labels are plain review language', () => {
    assert.equal(cleanupCategoryLabel('exact_duplicate'), 'Exact Duplicates');
    assert.equal(cleanupCategoryLabel('inactive_archive'), 'Archives');
    assert.equal(cleanupCategoryLabel('duplicate_resource_cfg'), 'Resource.cfg');
    assert.equal(cleanupCategoryLabel('support_file'), 'Support Files');
    assert.equal(cleanupCategoryLabel('misplaced_tray'), 'Tray Files');
    assert.equal(cleanupCategoryLabel('future_category'), 'future category');
});

test('cleanup action selection is stable and deduplicated', () => {
    assert.equal(typeof cleanupModel.selectAllCleanupActions, 'function');
    assert.equal(typeof cleanupModel.toggleCleanupAction, 'function');
    const actions = flattenCleanupActions(PLAN);

    assert.deepEqual(cleanupModel.selectAllCleanupActions(actions), [
        'duplicate:1',
        'inactive_archive:1:Mods/download.zip',
        'inactive_archive:1:Mods/old.rar',
    ]);
    assert.deepEqual(cleanupModel.toggleCleanupAction(['duplicate:1'], 'duplicate:1', true), ['duplicate:1']);
    assert.deepEqual(cleanupModel.toggleCleanupAction(['duplicate:1'], 'inactive_archive:1:Mods/download.zip', true), [
        'duplicate:1',
        'inactive_archive:1:Mods/download.zip',
    ]);
    assert.deepEqual(cleanupModel.toggleCleanupAction(['duplicate:1'], 'duplicate:1', false), []);
});

test('stage readiness requires exported plan and explicit action scope', () => {
    assert.equal(typeof cleanupModel.canStageCleanupOperation, 'function');
    assert.equal(
        cleanupModel.canStageCleanupOperation({
            planPath: '',
            selectedActionIds: ['duplicate:1'],
            allActions: false,
            actionCount: 3,
        }),
        false,
    );
    assert.equal(
        cleanupModel.canStageCleanupOperation({
            planPath: '/tmp/cleanup-plan.json',
            selectedActionIds: [],
            allActions: false,
            actionCount: 3,
        }),
        false,
    );
    assert.equal(
        cleanupModel.canStageCleanupOperation({
            planPath: '/tmp/cleanup-plan.json',
            selectedActionIds: ['duplicate:1'],
            allActions: true,
            actionCount: 3,
        }),
        false,
    );
    assert.equal(
        cleanupModel.canStageCleanupOperation({
            planPath: '/tmp/cleanup-plan.json',
            selectedActionIds: ['duplicate:1'],
            allActions: false,
            actionCount: 3,
        }),
        true,
    );
    assert.equal(
        cleanupModel.canStageCleanupOperation({
            planPath: '/tmp/cleanup-plan.json',
            selectedActionIds: [],
            allActions: true,
            actionCount: 3,
        }),
        true,
    );
});

test('cleanup operation summary preserves manifest counts and errors', () => {
    assert.equal(typeof cleanupModel.summarizeCleanupOperation, 'function');
    assert.deepEqual(cleanupModel.summarizeCleanupOperation(MANIFEST), {
        operationId: 'cleanup-op-20260612-101530',
        manifestPath: '/Sims/The Sims 4/_Simanalysis_Cleanup/manifests/cleanup-op-20260612-101530.json',
        status: 'partial',
        actionCount: 3,
        statusCounts: {
            moved: 1,
            blocked: 1,
            pending: 1,
        },
        warnings: ['Manifest warning'],
        blockers: ['The Sims 4 is running'],
        errors: ['Hash changed before apply'],
    });
});

test('cleanup operation apply and restore gates follow manifest status', () => {
    assert.equal(typeof cleanupModel.canApplyCleanupOperation, 'function');
    assert.equal(typeof cleanupModel.canRestoreCleanupOperation, 'function');
    assert.equal(cleanupModel.canApplyCleanupOperation({ status: 'planned', actions: [{ status: 'pending' }] }), true);
    assert.equal(cleanupModel.canApplyCleanupOperation({ status: 'partial', actions: [{ status: 'blocked' }] }), true);
    assert.equal(cleanupModel.canApplyCleanupOperation({ status: 'applied', actions: [{ status: 'moved' }] }), false);
    assert.equal(cleanupModel.canApplyCleanupOperation({ status: 'planned', actions: [] }), false);

    assert.equal(cleanupModel.canRestoreCleanupOperation({ status: 'applied', actions: [{ status: 'moved' }] }), true);
    assert.equal(cleanupModel.canRestoreCleanupOperation({ status: 'partial', actions: [{ status: 'restore_pending' }] }), true);
    assert.equal(cleanupModel.canRestoreCleanupOperation({ status: 'restored', actions: [{ status: 'restored' }] }), false);
    assert.equal(cleanupModel.canRestoreCleanupOperation({ status: 'planned', actions: [{ status: 'pending' }] }), false);
});
