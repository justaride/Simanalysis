import assert from 'node:assert/strict';
import test from 'node:test';

import {
    canRecordPatchBaseline,
    summarizePatchProfileWorkflow,
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

test('patch profile workflow recommends safe profile testing after a patch', () => {
    const workflow = summarizePatchProfileWorkflow(
        {
            status: 'changed',
            patch_detected: true,
            risk_classes: [{ id: 'script_mods', status: 'unknown_after_patch' }],
        },
        {
            active_sims4_profile: '/Profiles/Main/The Sims 4',
            sims4_profiles: ['/Profiles/Main/The Sims 4', '/Profiles/Vanilla Test/The Sims 4'],
        },
        '/Profiles/Main/The Sims 4',
    );

    assert.deepEqual(workflow, {
        activeProfile: '/Profiles/Main/The Sims 4',
        selectedProfile: '/Profiles/Main/The Sims 4',
        profileMatchesSelected: true,
        knownProfileCount: 2,
        profileStatusLabel: 'Active profile selected',
        profileTone: 'green',
        safeActionTitle: 'Use a separate test profile',
        safeActionBody: 'Keep unknown-after-patch mods disabled in your main profile until a vanilla test and save-copy test pass.',
        cacheRecommendationTitle: 'Run Cache Doctor after the patch test',
        cacheRecommendationBody: 'Review cache status and use reversible quarantine only after the game is closed and the patch test path is clear.',
        automaticReenableLabel: 'No automatic re-enable',
    });
});

test('patch profile workflow flags selected folder outside the active profile', () => {
    const workflow = summarizePatchProfileWorkflow(
        { status: 'unchanged', patch_detected: false, automatic_reenable: false },
        { active_sims4_profile: '/Profiles/Main/The Sims 4' },
        '/Profiles/Other/The Sims 4',
    );

    assert.equal(workflow.profileMatchesSelected, false);
    assert.equal(workflow.profileStatusLabel, 'Different folder selected');
    assert.equal(workflow.profileTone, 'amber');
    assert.equal(workflow.safeActionTitle, 'Verify profile before recording');
    assert.equal(workflow.cacheRecommendationTitle, 'Cache Doctor optional');
});
