export function summarizeMasterPlan(data = {}) {
    const summary = data?.summary || {};
    return {
        activeUnits: summary.active_units || 0,
        catalogEntries: summary.catalog_entries || 0,
        creatorProfiles: summary.creator_profiles || 0,
        performanceActions: summary.performance_actions || 0,
        updateCandidates: summary.update_candidates || 0,
        warnings: summary.warnings || 0,
    };
}

export function topCreatorProfiles(data = {}, limit = 8) {
    const profiles = data?.creators?.profiles || [];
    return [...profiles]
        .sort((a, b) => {
            const scriptDelta = (b.script_count || 0) - (a.script_count || 0);
            if (scriptDelta !== 0) return scriptDelta;
            const unitDelta = (b.unit_count || 0) - (a.unit_count || 0);
            if (unitDelta !== 0) return unitDelta;
            return String(a.creator || '').localeCompare(String(b.creator || ''));
        })
        .slice(0, limit);
}

export function summarizeBaselineStatus(data = {}) {
    const summary = data?.summary || {};
    return {
        added: summary.added || 0,
        baselineExists: Boolean(data?.baseline_exists),
        baselinePath: data?.baseline_path || null,
        changed: summary.changed || 0,
        removed: summary.removed || 0,
        unchanged: summary.unchanged || 0,
        warnings: summary.warnings || 0,
    };
}

export function baselineChangeCount(data = {}) {
    const summary = data?.summary || {};
    return (summary.added || 0) + (summary.removed || 0) + (summary.changed || 0);
}

export function summarizeUpdateRegistryStatus(data = {}) {
    const summary = data?.summary || {};
    return {
        catalogEntries: summary.catalog_entries || 0,
        current: summary.current || 0,
        missingSources: summary.missing_sources || 0,
        needsCheck: summary.needs_check || 0,
        noInstalledVersion: summary.no_installed_version || 0,
        outdated: summary.outdated || 0,
        registryExists: Boolean(data?.registry_exists),
        registryPath: data?.registry_path || null,
        retiredEntries: summary.retired_entries || 0,
        trackedSources: summary.tracked_sources || 0,
        warnings: summary.warnings || 0,
    };
}

export function updateRegistryActionCount(data = {}) {
    const summary = data?.summary || {};
    return (
        (summary.outdated || 0)
        + (summary.missing_sources || 0)
        + (summary.needs_check || 0)
        + (summary.no_installed_version || 0)
    );
}

export function updateRegistryAttentionEntries(data = {}, limit = 8) {
    const entries = data?.entries || [];
    return entries
        .filter((entry) => entry?.status && entry.status !== 'current')
        .slice(0, limit);
}
