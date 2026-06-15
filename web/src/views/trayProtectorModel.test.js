import assert from 'node:assert/strict';
import test from 'node:test';

import {
    summarizeTrayProtectorStatus,
    toTrayDependencyRows,
    toTrayGroupRows,
    toTraySignalRows,
} from './trayProtectorModel.js';

const TRAY_PAYLOAD = {
    status: 'review_recommended',
    root_path: '/Sims/The Sims 4',
    tray_path: '/Sims/The Sims 4/Tray',
    tray_file_count: 3,
    group_count: 2,
    anchored_group_count: 1,
    sidecar_only_group_count: 1,
    total_size_bytes: 4096,
    latest_modified_at: '2026-06-15T05:00:00Z',
    mutates_files: false,
    warnings: ['Skipped symlinked Tray entry: /Sims/The Sims 4/Tray/linked.trayitem'],
    recommendations: ['Treat Tray dependency signals as read-only evidence.'],
    signals: [
        {
            id: 'sidecar_without_trayitem',
            severity: 'medium',
            message: 'Tray sidecar files exist without a .trayitem anchor.',
            paths: ['Tray/orphan.bpi'],
        },
    ],
    groups: [
        {
            stem: 'orphan',
            file_count: 1,
            has_trayitem: false,
            type_hint: 'Sidecar group',
            total_size_bytes: 1024,
            latest_modified_at: '2026-06-15T04:00:00Z',
            extensions: ['.bpi'],
            dependency_signals: [
                {
                    id: 'probable_build_buy_sidecar_without_anchor',
                    dependency_kind: 'build_buy',
                    confidence: 'probable',
                    anchor_state: 'missing',
                    severity: 'medium',
                    message: 'Lot or room sidecar evidence suggests probable Build/Buy dependency scope, but the .trayitem anchor is missing.',
                    evidence: ['.bpi sidecar present'],
                },
            ],
            files: [
                {
                    name: 'orphan.bpi',
                    relative_path: 'Tray/orphan.bpi',
                    extension: '.bpi',
                    size_bytes: 1024,
                },
            ],
        },
        {
            stem: 'family',
            file_count: 2,
            has_trayitem: true,
            type_hint: 'Household',
            total_size_bytes: 3072,
            latest_modified_at: '2026-06-15T05:00:00Z',
            extensions: ['.hhi', '.trayitem'],
            files: [
                {
                    name: 'family.trayitem',
                    relative_path: 'Tray/family.trayitem',
                    extension: '.trayitem',
                    size_bytes: 2048,
                },
                {
                    name: 'family.hhi',
                    relative_path: 'Tray/family.hhi',
                    extension: '.hhi',
                    size_bytes: 1024,
                },
            ],
            dependency_signals: [
                {
                    id: 'likely_cas_dependency_scope',
                    dependency_kind: 'cas',
                    confidence: 'likely',
                    anchor_state: 'present',
                    severity: 'low',
                    message: 'Household Tray evidence suggests likely CAS dependency scope; this is not a missing dependency claim.',
                    evidence: ['.trayitem anchor present', '.hhi household sidecar present'],
                },
            ],
        },
    ],
};

test('tray protector summary preserves read-only status and counts', () => {
    assert.deepEqual(summarizeTrayProtectorStatus(TRAY_PAYLOAD), {
        status: 'review_recommended',
        statusLabel: 'Review recommended',
        tone: 'amber',
        rootPath: '/Sims/The Sims 4',
        trayPath: '/Sims/The Sims 4/Tray',
        trayFileCount: 3,
        groupCount: 2,
        anchoredGroupCount: 1,
        sidecarOnlyGroupCount: 1,
        totalSizeBytes: 4096,
        totalSizeLabel: '4 KB',
        latestModifiedAt: '2026-06-15T05:00:00Z',
        warningCount: 1,
        signalCount: 1,
        recommendationCount: 1,
        readOnlyLabel: 'Read-only',
    });
});

test('tray group rows sort anchored groups first and keep dependency context', () => {
    assert.deepEqual(toTrayGroupRows(TRAY_PAYLOAD), [
        {
            id: 'family',
            stem: 'family',
            anchorLabel: 'Anchored',
            hasTrayitem: true,
            typeHint: 'Household',
            fileCount: 2,
            extensionsLabel: '.hhi, .trayitem',
            totalSizeBytes: 3072,
            totalSizeLabel: '3 KB',
            latestModifiedAt: '2026-06-15T05:00:00Z',
        },
        {
            id: 'orphan',
            stem: 'orphan',
            anchorLabel: 'Sidecar only',
            hasTrayitem: false,
            typeHint: 'Sidecar group',
            fileCount: 1,
            extensionsLabel: '.bpi',
            totalSizeBytes: 1024,
            totalSizeLabel: '1 KB',
            latestModifiedAt: '2026-06-15T04:00:00Z',
        },
    ]);
});

test('tray signal rows preserve severity and path lists', () => {
    assert.deepEqual(toTraySignalRows(TRAY_PAYLOAD), [
        {
            id: 'sidecar_without_trayitem-0',
            label: 'Sidecar Without Trayitem',
            severity: 'medium',
            severityLabel: 'Medium',
            message: 'Tray sidecar files exist without a .trayitem anchor.',
            location: 'Tray/orphan.bpi',
        },
    ]);
});

test('tray dependency rows flatten calibrated group signals', () => {
    assert.deepEqual(toTrayDependencyRows(TRAY_PAYLOAD), [
        {
            id: 'family-likely_cas_dependency_scope-0',
            group: 'family',
            dependencyKind: 'CAS',
            confidence: 'likely',
            confidenceLabel: 'Likely',
            anchorState: 'present',
            severity: 'low',
            severityLabel: 'Low',
            message: 'Household Tray evidence suggests likely CAS dependency scope; this is not a missing dependency claim.',
            evidenceLabel: '.trayitem anchor present; .hhi household sidecar present',
        },
        {
            id: 'orphan-probable_build_buy_sidecar_without_anchor-0',
            group: 'orphan',
            dependencyKind: 'Build/Buy',
            confidence: 'probable',
            confidenceLabel: 'Probable',
            anchorState: 'missing',
            severity: 'medium',
            severityLabel: 'Medium',
            message: 'Lot or room sidecar evidence suggests probable Build/Buy dependency scope, but the .trayitem anchor is missing.',
            evidenceLabel: '.bpi sidecar present',
        },
    ]);
});

test('tray protector model falls back without inventing mutation support', () => {
    assert.equal(summarizeTrayProtectorStatus({}).readOnlyLabel, 'Read-only');
    assert.equal(
        summarizeTrayProtectorStatus({ mutates_files: true }).readOnlyLabel,
        'Mutation reported',
    );
    assert.deepEqual(toTrayGroupRows({}), []);
    assert.deepEqual(toTraySignalRows({}), []);
    assert.deepEqual(toTrayDependencyRows({}), []);
});
