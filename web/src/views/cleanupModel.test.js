import assert from 'node:assert/strict';
import test from 'node:test';

import {
    cleanupCategoryLabel,
    flattenCleanupActions,
    summarizeCleanupPlan,
} from './cleanupModel.js';

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
