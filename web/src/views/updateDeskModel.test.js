import assert from 'node:assert/strict';
import test from 'node:test';

import {
    canCommitUpdatePlan,
    getCommitEligibleUpdateActionRows,
    summarizeUpdateInstallPlan,
    summarizeUpdateOperation,
    summarizeUpdateDeskStatus,
    toggleUpdateActionSelection,
    toUpdatePlanActionRows,
    toUpdateItemRows,
    toUpdateSignalRows,
} from './updateDeskModel.js';

const UPDATE_PAYLOAD = {
    status: 'review_recommended',
    staging_path: '/Profiles/Main/Simanalysis Staging',
    item_count: 2,
    archive_count: 1,
    package_count: 1,
    script_count: 0,
    other_count: 0,
    source_bound_count: 1,
    missing_source_count: 1,
    total_size_bytes: 4096,
    latest_modified_at: '2026-06-15T07:00:00Z',
    mutates_files: false,
    warnings: ['Skipped symlinked staging entry: /Profiles/Main/Simanalysis Staging/linked.package'],
    recommendations: ['Keep external downloads in staging until an install plan has been reviewed.'],
    signals: [
        {
            id: 'archive_path_escape',
            severity: 'high',
            message: 'Archive contains absolute or parent-directory member paths.',
            path: 'unsafe.zip',
            paths: ['../escape.package'],
        },
    ],
    items: [
        {
            name: 'loose.package',
            relative_path: 'loose.package',
            kind: 'package',
            extension: '.package',
            size_bytes: 1024,
            modified_at: '2026-06-15T06:00:00Z',
            source_binding: { status: 'missing' },
            archive_scan: { status: 'not_archive' },
        },
        {
            name: 'cool_mod.zip',
            relative_path: 'cool_mod.zip',
            kind: 'archive',
            extension: '.zip',
            size_bytes: 3072,
            modified_at: '2026-06-15T07:00:00Z',
            source_binding: {
                status: 'bound',
                source_url: 'https://example.test/cool',
                creator: 'Example Creator',
            },
            archive_scan: {
                status: 'readable_zip',
                member_count: 3,
                unsafe_members: [],
            },
        },
    ],
};

const UPDATE_PLAN = {
    version: 1,
    plan_id: 'update-plan-20260615T0715',
    generated_at: '2026-06-15T07:15:00Z',
    status: 'ready_for_review',
    staging_status: 'review_recommended',
    staging_path: '/Profiles/Main/Simanalysis Staging',
    mods_path: '/Profiles/Main/The Sims 4/Mods',
    manifest_path: null,
    action_count: 3,
    copy_count: 2,
    archive_review_count: 1,
    blocked_count: 0,
    requires_snapshot: true,
    mutates_files: false,
    mutates_mods: false,
    warnings: [],
    recommendations: [
        'Review this plan before any snapshot-backed commit step.',
    ],
    actions: [
        {
            action_id: 'update-copy-001',
            action_type: 'copy_staged_file',
            status: 'planned',
            source_name: 'loose.package',
            source_relative_path: 'loose.package',
            destination_relative_path: 'loose.package',
            expected: { size: 2048, sha256: 'abc123' },
            source_binding: { status: 'bound', creator: 'Creator' },
            archive_scan: { status: 'not_archive' },
            blockers: [],
            review_notes: [],
        },
        {
            action_id: 'update-archive-002',
            action_type: 'review_archive',
            status: 'review_required',
            source_name: 'cool.zip',
            source_relative_path: 'cool.zip',
            destination_relative_path: null,
            expected: { size: 4096, sha256: 'def456' },
            source_binding: { status: 'missing' },
            archive_scan: { status: 'readable_zip', member_count: 2 },
            blockers: [],
            review_notes: ['archive_requires_explicit_review'],
        },
    ],
};

test('update desk summary preserves read-only status and counts', () => {
    assert.deepEqual(summarizeUpdateDeskStatus(UPDATE_PAYLOAD), {
        status: 'review_recommended',
        statusLabel: 'Review recommended',
        tone: 'amber',
        stagingPath: '/Profiles/Main/Simanalysis Staging',
        itemCount: 2,
        archiveCount: 1,
        packageCount: 1,
        scriptCount: 0,
        otherCount: 0,
        sourceBoundCount: 1,
        missingSourceCount: 1,
        totalSizeBytes: 4096,
        totalSizeLabel: '4 KB',
        latestModifiedAt: '2026-06-15T07:00:00Z',
        warningCount: 1,
        signalCount: 1,
        recommendationCount: 1,
        readOnlyLabel: 'Read-only',
    });
});

test('update item rows sort mod candidates before other files and keep source context', () => {
    assert.deepEqual(toUpdateItemRows(UPDATE_PAYLOAD), [
        {
            id: 'cool_mod.zip',
            name: 'cool_mod.zip',
            kind: 'archive',
            kindLabel: 'Archive',
            extension: '.zip',
            sourceStatus: 'bound',
            sourceLabel: 'Bound',
            archiveStatus: 'readable_zip',
            archiveLabel: 'Readable Zip',
            memberCount: 3,
            sizeBytes: 3072,
            sizeLabel: '3 KB',
            latestModifiedAt: '2026-06-15T07:00:00Z',
        },
        {
            id: 'loose.package',
            name: 'loose.package',
            kind: 'package',
            kindLabel: 'Package',
            extension: '.package',
            sourceStatus: 'missing',
            sourceLabel: 'Missing',
            archiveStatus: 'not_archive',
            archiveLabel: 'Not Archive',
            memberCount: null,
            sizeBytes: 1024,
            sizeLabel: '1 KB',
            latestModifiedAt: '2026-06-15T06:00:00Z',
        },
    ]);
});

test('update signal rows preserve severity and archive member context', () => {
    assert.deepEqual(toUpdateSignalRows(UPDATE_PAYLOAD), [
        {
            id: 'archive_path_escape-0',
            label: 'Archive Path Escape',
            severity: 'high',
            severityLabel: 'High',
            message: 'Archive contains absolute or parent-directory member paths.',
            location: 'unsafe.zip',
            detail: '../escape.package',
        },
    ]);
});

test('update install plan summary preserves snapshot and mutation gates', () => {
    assert.deepEqual(summarizeUpdateInstallPlan(UPDATE_PLAN), {
        status: 'ready_for_review',
        statusLabel: 'Ready for review',
        tone: 'green',
        planId: 'update-plan-20260615T0715',
        generatedAt: '2026-06-15T07:15:00Z',
        stagingPath: '/Profiles/Main/Simanalysis Staging',
        modsPath: '/Profiles/Main/The Sims 4/Mods',
        manifestPath: null,
        actionCount: 3,
        copyCount: 2,
        archiveReviewCount: 1,
        blockedCount: 0,
        warningCount: 0,
        recommendationCount: 1,
        requiresSnapshotLabel: 'Snapshot required',
        readOnlyLabel: 'Read-only',
        modsMutationLabel: 'No Mods mutation',
    });
});

test('update install plan action rows keep blockers and review-only archive actions visible', () => {
    assert.deepEqual(toUpdatePlanActionRows(UPDATE_PLAN), [
        {
            id: 'update-copy-001',
            type: 'copy_staged_file',
            typeLabel: 'Copy Staged File',
            status: 'planned',
            statusLabel: 'Planned',
            sourceName: 'loose.package',
            sourceRelativePath: 'loose.package',
            destinationRelativePath: 'loose.package',
            expectedSizeLabel: '2 KB',
            sourceStatus: 'bound',
            sourceLabel: 'Bound',
            archiveStatus: 'not_archive',
            archiveLabel: 'Not Archive',
            blockers: [],
            reviewNotes: [],
        },
        {
            id: 'update-archive-002',
            type: 'review_archive',
            typeLabel: 'Review Archive',
            status: 'review_required',
            statusLabel: 'Review Required',
            sourceName: 'cool.zip',
            sourceRelativePath: 'cool.zip',
            destinationRelativePath: 'Review archive contents',
            expectedSizeLabel: '4 KB',
            sourceStatus: 'missing',
            sourceLabel: 'Missing',
            archiveStatus: 'readable_zip',
            archiveLabel: 'Readable Zip',
            blockers: [],
            reviewNotes: ['archive_requires_explicit_review'],
        },
    ]);
});

test('update install plan exposes only planned copy actions as commit eligible', () => {
    const rows = toUpdatePlanActionRows(UPDATE_PLAN);

    assert.deepEqual(getCommitEligibleUpdateActionRows(rows), [
        {
            id: 'update-copy-001',
            type: 'copy_staged_file',
            typeLabel: 'Copy Staged File',
            status: 'planned',
            statusLabel: 'Planned',
            sourceName: 'loose.package',
            sourceRelativePath: 'loose.package',
            destinationRelativePath: 'loose.package',
            expectedSizeLabel: '2 KB',
            sourceStatus: 'bound',
            sourceLabel: 'Bound',
            archiveStatus: 'not_archive',
            archiveLabel: 'Not Archive',
            blockers: [],
            reviewNotes: [],
        },
    ]);
});

test('update action selection toggles explicit copy actions without duplicates', () => {
    assert.deepEqual(toggleUpdateActionSelection([], 'update-copy-001', true), [
        'update-copy-001',
    ]);
    assert.deepEqual(
        toggleUpdateActionSelection(['update-copy-001'], 'update-copy-001', true),
        ['update-copy-001'],
    );
    assert.deepEqual(
        toggleUpdateActionSelection(['update-copy-001', 'update-copy-002'], 'update-copy-001', false),
        ['update-copy-002'],
    );
});

test('update commit gate requires a saved plan path and explicit selected actions', () => {
    assert.equal(
        canCommitUpdatePlan({
            planPath: '/tmp/update-plan.json',
            selectedActionIds: ['update-copy-001'],
            eligibleActionCount: 1,
        }),
        true,
    );
    assert.equal(
        canCommitUpdatePlan({
            planPath: '',
            selectedActionIds: ['update-copy-001'],
            eligibleActionCount: 1,
        }),
        false,
    );
    assert.equal(
        canCommitUpdatePlan({
            planPath: '/tmp/update-plan.json',
            selectedActionIds: [],
            eligibleActionCount: 1,
        }),
        false,
    );
    assert.equal(
        canCommitUpdatePlan({
            planPath: '/tmp/update-plan.json',
            selectedActionIds: ['update-copy-001'],
            eligibleActionCount: 0,
        }),
        false,
    );
});

test('update operation summary exposes manifest status and undo availability', () => {
    assert.deepEqual(
        summarizeUpdateOperation({
            operation_id: 'update-op-001',
            status: 'applied',
            manifest_path: '/Mods/_Simanalysis_UpdateDesk/manifests/update-op-001.json',
            actions: [
                { action_id: 'update-copy-001', status: 'copied' },
                { action_id: 'update-copy-002', status: 'blocked', error: 'destination exists' },
            ],
            warnings: ['review cache after install'],
            blockers: ['destination exists'],
        }),
        {
            operationId: 'update-op-001',
            status: 'applied',
            statusLabel: 'Applied',
            tone: 'green',
            manifestPath: '/Mods/_Simanalysis_UpdateDesk/manifests/update-op-001.json',
            copiedCount: 1,
            blockedCount: 1,
            undoneCount: 0,
            warningCount: 1,
            blockerCount: 1,
            canUndo: true,
        },
    );
    assert.equal(summarizeUpdateOperation({ status: 'undone' }).canUndo, false);
});

test('update desk model falls back without inventing mutation support', () => {
    assert.equal(summarizeUpdateDeskStatus({}).readOnlyLabel, 'Read-only');
    assert.equal(
        summarizeUpdateDeskStatus({ mutates_files: true }).readOnlyLabel,
        'Mutation reported',
    );
    assert.deepEqual(toUpdateItemRows({}), []);
    assert.deepEqual(toUpdateSignalRows({}), []);
    assert.equal(summarizeUpdateInstallPlan({}).readOnlyLabel, 'Read-only');
    assert.equal(summarizeUpdateInstallPlan({ mutates_mods: true }).modsMutationLabel, 'Mods mutation reported');
    assert.deepEqual(toUpdatePlanActionRows({}), []);
    assert.deepEqual(getCommitEligibleUpdateActionRows([]), []);
    assert.deepEqual(summarizeUpdateOperation({}).statusLabel, 'No operation');
});
