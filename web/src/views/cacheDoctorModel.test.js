import assert from 'node:assert/strict';
import test from 'node:test';

import {
    summarizeCacheStatus,
    toCacheTargetRows,
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
