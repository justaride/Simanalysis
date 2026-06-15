import assert from 'node:assert/strict';
import test from 'node:test';

import {
    canRecordPatchBaseline,
    summarizePatchDayStatus,
    toPatchRiskRows,
} from './patchDayModel.js';

test('patch day summary labels changed game versions honestly', () => {
    const summary = summarizePatchDayStatus({
        status: 'changed',
        patch_detected: true,
        current_game_version: '1.108.329.1020',
        last_known_game_version: '1.107.151.1020',
        automatic_reenable: false,
        risk_classes: [
            { id: 'script_mods', label: 'Script mods', status: 'unknown_after_patch' },
            { id: 'ui_mods', label: 'UI mods', status: 'unknown_after_patch' },
        ],
        recommendations: ['Run a vanilla test before re-enabling mods.'],
        warnings: [],
    });

    assert.deepEqual(summary, {
        status: 'changed',
        statusLabel: 'Patch detected',
        tone: 'amber',
        patchDetected: true,
        currentVersion: '1.108.329.1020',
        lastKnownVersion: '1.107.151.1020',
        riskCount: 2,
        recommendationCount: 1,
        warningCount: 0,
        automaticReenableLabel: 'No automatic re-enable',
    });
});

test('patch day summary keeps missing GameVersion distinct', () => {
    const summary = summarizePatchDayStatus({
        status: 'missing_game_version',
        patch_detected: false,
        warnings: ['GameVersion.txt was not found in the selected Sims 4 folder.'],
    });

    assert.equal(summary.statusLabel, 'GameVersion.txt missing');
    assert.equal(summary.tone, 'red');
    assert.equal(summary.currentVersion, 'unknown');
    assert.equal(summary.warningCount, 1);
});

test('patch day risk rows preserve labels and reasons', () => {
    assert.deepEqual(
        toPatchRiskRows({
            risk_classes: [
                {
                    id: 'script_mods',
                    label: 'Script mods',
                    status: 'unknown_after_patch',
                    reason: 'Game version changed.',
                },
            ],
        }),
        [
            {
                id: 'script_mods',
                label: 'Script mods',
                status: 'unknown_after_patch',
                statusLabel: 'Unknown after patch',
                reason: 'Game version changed.',
            },
        ],
    );
});

test('patch day baseline recording requires a current game version', () => {
    assert.equal(canRecordPatchBaseline({ current_game_version: '1.108.329.1020' }), true);
    assert.equal(canRecordPatchBaseline({ current_game_version: null }), false);
});
