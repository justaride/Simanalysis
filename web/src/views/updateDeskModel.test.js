import assert from 'node:assert/strict';
import test from 'node:test';

import {
    summarizeUpdateDeskStatus,
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

test('update desk model falls back without inventing mutation support', () => {
    assert.equal(summarizeUpdateDeskStatus({}).readOnlyLabel, 'Read-only');
    assert.equal(
        summarizeUpdateDeskStatus({ mutates_files: true }).readOnlyLabel,
        'Mutation reported',
    );
    assert.deepEqual(toUpdateItemRows({}), []);
    assert.deepEqual(toUpdateSignalRows({}), []);
});
