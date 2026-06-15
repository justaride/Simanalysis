import assert from 'node:assert/strict';
import test from 'node:test';

import {
    dashboardStats,
    fileTypeDistribution,
    formatDashboardBytes,
    severityCounts,
} from './dashboardModel.js';

const SCAN_RESULT = {
    summary: {
        total_mods: 4,
    },
    mods: [
        { name: 'A.package', path: '/Mods/A.package', type: 'package', size: 1024 },
        { name: 'B.package', path: '/Mods/B.package', type: 'package', size: 2048 },
        { name: 'C.ts4script', path: '/Mods/C.ts4script', type: 'script', size: 4096 },
        { name: 'Readme.txt', path: '/Mods/Readme.txt', type: 'other', size: 512 },
    ],
    conflicts: [
        { severity: 'critical' },
        { severity: 'high' },
        { severity: 'high' },
        { severity: 'low' },
    ],
};

test('dashboard severity counts use actual conflict rows', () => {
    assert.deepEqual(severityCounts(SCAN_RESULT.conflicts), {
        critical: 1,
        high: 2,
        medium: 0,
        low: 1,
    });
});

test('dashboard file distribution is derived from scanned mods', () => {
    assert.deepEqual(fileTypeDistribution(SCAN_RESULT), [
        { name: '.package', value: 2 },
        { name: '.ts4script', value: 1 },
        { name: '.txt', value: 1 },
    ]);
});

test('dashboard stats remove placeholder totals', () => {
    assert.deepEqual(dashboardStats(SCAN_RESULT), {
        totalFiles: 4,
        totalSizeBytes: 7680,
        totalSizeLabel: '7.5 KB',
        severityCounts: {
            critical: 1,
            high: 2,
            medium: 0,
            low: 1,
        },
        fileTypes: [
            { name: '.package', value: 2 },
            { name: '.ts4script', value: 1 },
            { name: '.txt', value: 1 },
        ],
        healthScore: 80,
    });
});

test('dashboard stats fall back without inventing scan data', () => {
    assert.deepEqual(dashboardStats({}), {
        totalFiles: 0,
        totalSizeBytes: 0,
        totalSizeLabel: '0 B',
        severityCounts: {
            critical: 0,
            high: 0,
            medium: 0,
            low: 0,
        },
        fileTypes: [],
        healthScore: 100,
    });
});

test('dashboard bytes format compactly', () => {
    assert.equal(formatDashboardBytes(0), '0 B');
    assert.equal(formatDashboardBytes(512), '512 B');
    assert.equal(formatDashboardBytes(1536), '1.5 KB');
    assert.equal(formatDashboardBytes(1048576), '1 MB');
});
