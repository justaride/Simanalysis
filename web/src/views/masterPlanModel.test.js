import test from 'node:test';
import assert from 'node:assert/strict';
import {
    baselineChangeCount,
    summarizeUpdateRegistryStatus,
    summarizeBaselineStatus,
    summarizeMasterPlan,
    topCreatorProfiles,
    updateRegistryActionCount,
    updateRegistryAttentionEntries,
} from './masterPlanModel.js';

test('summarizeMasterPlan handles empty initial state', () => {
    assert.deepEqual(summarizeMasterPlan(null), {
        activeUnits: 0,
        catalogEntries: 0,
        creatorProfiles: 0,
        performanceActions: 0,
        updateCandidates: 0,
        warnings: 0,
    });
});

test('summarizeMasterPlan maps backend summary keys', () => {
    assert.deepEqual(
        summarizeMasterPlan({
            summary: {
                active_units: 12,
                catalog_entries: 10,
                creator_profiles: 4,
                performance_actions: 2,
                update_candidates: 3,
                warnings: 1,
            },
        }),
        {
            activeUnits: 12,
            catalogEntries: 10,
            creatorProfiles: 4,
            performanceActions: 2,
            updateCandidates: 3,
            warnings: 1,
        },
    );
});

test('topCreatorProfiles sorts and bounds creator rows', () => {
    const profiles = topCreatorProfiles(
        {
            creators: {
                profiles: [
                    { creator: 'B', unit_count: 1, script_count: 0 },
                    { creator: 'A', unit_count: 3, script_count: 2 },
                    { creator: 'C', unit_count: 2, script_count: 2 },
                ],
            },
        },
        2,
    );

    assert.deepEqual(profiles.map((profile) => profile.creator), ['A', 'C']);
});

test('summarizeBaselineStatus handles missing baseline state', () => {
    assert.deepEqual(summarizeBaselineStatus(null), {
        added: 0,
        baselineExists: false,
        baselinePath: null,
        changed: 0,
        removed: 0,
        unchanged: 0,
        warnings: 0,
    });
});

test('summarizeBaselineStatus maps diff summaries', () => {
    assert.deepEqual(
        summarizeBaselineStatus({
            baseline_exists: true,
            baseline_path: '/tmp/latest.json',
            summary: {
                added: 2,
                removed: 1,
                changed: 3,
                unchanged: 4,
                warnings: 1,
            },
        }),
        {
            added: 2,
            baselineExists: true,
            baselinePath: '/tmp/latest.json',
            changed: 3,
            removed: 1,
            unchanged: 4,
            warnings: 1,
        },
    );
});

test('baselineChangeCount counts actionable changes', () => {
    assert.equal(
        baselineChangeCount({
            summary: {
                added: 2,
                removed: 1,
                changed: 3,
                unchanged: 4,
            },
        }),
        6,
    );
});

test('summarizeUpdateRegistryStatus handles missing registry state', () => {
    assert.deepEqual(summarizeUpdateRegistryStatus(null), {
        catalogEntries: 0,
        current: 0,
        missingSources: 0,
        needsCheck: 0,
        noInstalledVersion: 0,
        outdated: 0,
        registryExists: false,
        registryPath: null,
        retiredEntries: 0,
        trackedSources: 0,
        warnings: 0,
    });
});

test('summarizeUpdateRegistryStatus maps backend summary keys', () => {
    assert.deepEqual(
        summarizeUpdateRegistryStatus({
            registry_exists: true,
            registry_path: '/tmp/update-registry.json',
            summary: {
                catalog_entries: 10,
                tracked_sources: 7,
                missing_sources: 3,
                outdated: 2,
                current: 4,
                needs_check: 1,
                no_installed_version: 1,
                retired_entries: 5,
                warnings: 1,
            },
        }),
        {
            catalogEntries: 10,
            current: 4,
            missingSources: 3,
            needsCheck: 1,
            noInstalledVersion: 1,
            outdated: 2,
            registryExists: true,
            registryPath: '/tmp/update-registry.json',
            retiredEntries: 5,
            trackedSources: 7,
            warnings: 1,
        },
    );
});

test('update registry helpers expose actionable rows', () => {
    const data = {
        summary: {
            missing_sources: 3,
            needs_check: 1,
            no_installed_version: 1,
            outdated: 2,
        },
        entries: [
            { unit_name: 'Current', status: 'current' },
            { unit_name: 'Outdated', status: 'outdated' },
            { unit_name: 'Missing', status: 'missing_source' },
        ],
    };

    assert.equal(updateRegistryActionCount(data), 7);
    assert.deepEqual(updateRegistryAttentionEntries(data, 2).map((entry) => entry.unit_name), [
        'Outdated',
        'Missing',
    ]);
});
