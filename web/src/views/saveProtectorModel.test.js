import assert from 'node:assert/strict';
import test from 'node:test';

import {
    summarizeSaveLaunchGuidance,
    summarizeSaveProtectorStatus,
    toSaveGroupRows,
    toSaveSignalRows,
} from './saveProtectorModel.js';

const SAVE_PAYLOAD = {
    status: 'review_recommended',
    root_path: '/Sims/The Sims 4',
    saves_path: '/Sims/The Sims 4/saves',
    primary_save_count: 1,
    backup_count: 2,
    orphan_backup_count: 1,
    total_size_bytes: 2048,
    latest_modified_at: '2026-06-15T04:00:00Z',
    mutates_files: false,
    warnings: ['Skipped symlinked save entry: /Sims/The Sims 4/saves/Slot_00000003.save'],
    recommendations: ['Make a manual save copy before patch-day testing or mod changes.'],
    signals: [
        {
            id: 'icloud_placeholder',
            severity: 'medium',
            message: 'iCloud placeholder or evicted file marker found in saves.',
            path: 'saves/Slot_00000004.save.icloud',
        },
    ],
    save_groups: [
        {
            slot: 'Slot_00000002',
            primary: null,
            backups: [
                {
                    name: 'Slot_00000002.save.ver0',
                    relative_path: 'saves/Slot_00000002.save.ver0',
                    size_bytes: 512,
                    modified_at: '2026-06-15T03:00:00Z',
                },
            ],
            backup_count: 1,
            total_size_bytes: 512,
            latest_modified_at: '2026-06-15T03:00:00Z',
        },
        {
            slot: 'Slot_00000001',
            primary: {
                name: 'Slot_00000001.save',
                relative_path: 'saves/Slot_00000001.save',
                size_bytes: 1024,
                modified_at: '2026-06-15T04:00:00Z',
            },
            backups: [
                {
                    name: 'Slot_00000001.save.ver0',
                    relative_path: 'saves/Slot_00000001.save.ver0',
                    size_bytes: 512,
                    modified_at: '2026-06-15T02:00:00Z',
                },
            ],
            backup_count: 1,
            total_size_bytes: 1536,
            latest_modified_at: '2026-06-15T04:00:00Z',
        },
    ],
};

test('save protector summary preserves read-only status and counts', () => {
    assert.deepEqual(summarizeSaveProtectorStatus(SAVE_PAYLOAD), {
        status: 'review_recommended',
        statusLabel: 'Review recommended',
        tone: 'amber',
        rootPath: '/Sims/The Sims 4',
        savesPath: '/Sims/The Sims 4/saves',
        primarySaveCount: 1,
        backupCount: 2,
        orphanBackupCount: 1,
        totalSizeBytes: 2048,
        totalSizeLabel: '2 KB',
        latestModifiedAt: '2026-06-15T04:00:00Z',
        warningCount: 1,
        signalCount: 1,
        recommendationCount: 1,
        readOnlyLabel: 'Read-only',
    });
});

test('save group rows sort primaries first and flag orphan backup groups', () => {
    assert.deepEqual(toSaveGroupRows(SAVE_PAYLOAD), [
        {
            id: 'Slot_00000001',
            slot: 'Slot_00000001',
            primaryName: 'Slot_00000001.save',
            primaryPath: 'saves/Slot_00000001.save',
            hasPrimary: true,
            backupCount: 1,
            totalSizeBytes: 1536,
            totalSizeLabel: '1.5 KB',
            latestModifiedAt: '2026-06-15T04:00:00Z',
        },
        {
            id: 'Slot_00000002',
            slot: 'Slot_00000002',
            primaryName: 'No primary save',
            primaryPath: '',
            hasPrimary: false,
            backupCount: 1,
            totalSizeBytes: 512,
            totalSizeLabel: '512 B',
            latestModifiedAt: '2026-06-15T03:00:00Z',
        },
    ]);
});

test('save signal rows preserve severity, paths, and fallback labels', () => {
    assert.deepEqual(toSaveSignalRows(SAVE_PAYLOAD), [
        {
            id: 'icloud_placeholder-0',
            label: 'Icloud Placeholder',
            severity: 'medium',
            severityLabel: 'Medium',
            message: 'iCloud placeholder or evicted file marker found in saves.',
            location: 'saves/Slot_00000004.save.icloud',
        },
    ]);
});

test('save protector model falls back without inventing mutation support', () => {
    assert.equal(summarizeSaveProtectorStatus({}).readOnlyLabel, 'Read-only');
    assert.equal(
        summarizeSaveProtectorStatus({ mutates_files: true }).readOnlyLabel,
        'Mutation reported',
    );
    assert.deepEqual(toSaveGroupRows({}), []);
    assert.deepEqual(toSaveSignalRows({}), []);
});

test('save launch guidance uses profile and patch evidence conservatively', () => {
    assert.deepEqual(
        summarizeSaveLaunchGuidance(
            SAVE_PAYLOAD,
            { active_sims4_profile: '/Sims/The Sims 4' },
            {
                status: 'changed',
                patch_detected: true,
                risk_classes: [{ id: 'script_mods', status: 'unknown_after_patch' }],
            },
            '/Sims/The Sims 4',
        ),
        {
            status: 'test_copy_recommended',
            statusLabel: 'Test copy recommended',
            tone: 'amber',
            profileStatusLabel: 'Active profile selected',
            profileTone: 'green',
            activeProfile: '/Sims/The Sims 4',
            selectedProfile: '/Sims/The Sims 4',
            patchEvidenceLabel: 'Unknown after patch',
            launchTitle: 'Launch only with a save copy',
            launchBody: 'These saves are likely tied to the active profile, but patch evidence is unknown-after-patch. Use a copied save for testing before opening important saves.',
            actionItems: [
                'Keep the original save files read-only in Simanalysis.',
                'Use a manual copy or future manifest-backed test-copy workflow before launch.',
                'Do not assume missing mods are safe after a game patch.',
            ],
        },
    );
});

test('save launch guidance flags missing profile or patch evidence', () => {
    const guidance = summarizeSaveLaunchGuidance(
        SAVE_PAYLOAD,
        { active_sims4_profile: '/Profiles/Main/The Sims 4' },
        {},
        '/Profiles/Other/The Sims 4',
    );

    assert.equal(guidance.status, 'missing_evidence');
    assert.equal(guidance.profileStatusLabel, 'Different folder selected');
    assert.equal(guidance.patchEvidenceLabel, 'Patch evidence missing');
    assert.match(guidance.launchBody, /evidence is missing/);
});

test('save launch guidance treats missing game version as missing evidence', () => {
    const guidance = summarizeSaveLaunchGuidance(
        SAVE_PAYLOAD,
        { active_sims4_profile: '/Sims/The Sims 4' },
        { status: 'missing_game_version' },
        '/Sims/The Sims 4',
    );

    assert.equal(guidance.status, 'missing_evidence');
    assert.equal(guidance.patchEvidenceLabel, 'Game version missing');
});
