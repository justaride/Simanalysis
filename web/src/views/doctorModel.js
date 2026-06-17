const STATUS_LABELS = {
    needs_action: 'Needs action',
    needs_review: 'Needs review',
    partial: 'Partial',
    clean: 'Clean',
};

const SEVERITY_LABELS = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    info: 'Info',
};

const CONFIDENCE_LABELS = {
    direct: 'Direct',
    partial: 'Partial',
};

const ACTION_LABELS = {
    start_bisect: 'Start Bisect',
    review_doctor_inputs: 'Review Inputs',
    review_doctor: 'Review Doctor',
    none: 'No action',
};

const VERDICT_TONES = {
    high: 'red',
    medium: 'amber',
    low: 'blue',
    info: 'green',
};

function asArray(value) {
    return Array.isArray(value) ? value : [];
}

function labelFor(mapping, value) {
    const key = String(value || '');
    return mapping[key] || key.replaceAll('_', ' ') || 'Unknown';
}

function titleLabel(value) {
    const label = labelFor({}, value);
    return `${label.slice(0, 1).toUpperCase()}${label.slice(1)}`;
}

function doctorKindLabel(kind) {
    if (kind === 'ui') return 'UI';
    return titleLabel(kind);
}

function formatEvidence(evidence) {
    return asArray(evidence)
        .map((item) => {
            if (!item || typeof item !== 'object') return null;
            const label = item.label || 'Evidence';
            const value = item.value ?? 0;
            return `${label}: ${value}`;
        })
        .filter(Boolean);
}

function basename(path) {
    const value = String(path || '');
    return value.split(/[\\/]/).filter(Boolean).pop() || value || 'Unknown source';
}

function count(value) {
    return Number.isFinite(value) ? value : 0;
}

export function summarizeDoctorVerdicts(result = {}) {
    return asArray(result?.verdicts).map((verdict) => {
        const severity = verdict?.severity || 'info';
        const status = verdict?.status || 'unknown';
        const confidence = verdict?.confidence || 'unknown';
        const nextAction = verdict?.recommended_next_action || null;
        return {
            id: verdict?.id || `${status}-${severity}`,
            title: verdict?.title || 'Doctor verdict',
            status,
            statusLabel: labelFor(STATUS_LABELS, status),
            severity,
            severityLabel: labelFor(SEVERITY_LABELS, severity),
            confidence,
            confidenceLabel: labelFor(CONFIDENCE_LABELS, confidence),
            nextAction,
            nextActionLabel: nextAction ? labelFor(ACTION_LABELS, nextAction) : null,
            tone: VERDICT_TONES[severity] || 'blue',
            evidence: formatEvidence(verdict?.evidence),
        };
    });
}

export function summarizeDoctorPlaybooks(result = {}) {
    return asArray(result?.playbooks).map((playbook) => ({
        id: playbook?.id || playbook?.title || 'doctor-playbook',
        title: playbook?.title || 'Doctor playbook',
        symptom: titleLabel(playbook?.symptom),
        available: playbook?.available !== false,
        nextCommand: playbook?.next_command || '',
        requires: asArray(playbook?.requires),
        reason: playbook?.reason || '',
    }));
}

export function summarizeDoctorTimeline(result = {}) {
    return asArray(result?.timeline).map((event) => {
        const kind = event?.kind || 'unknown';
        const created = event?.created || '';
        const sourceFile = event?.source_file || '';
        return {
            id: `${kind}-${created}-${sourceFile}`,
            kind,
            kindLabel: doctorKindLabel(kind),
            created,
            sourceFile,
            sourceName: basename(sourceFile),
            message: event?.message || '',
        };
    });
}

function collectScriptEvidence(result) {
    const byMod = {};
    const findings = result?.script_crashes?.findings || [];
    findings.forEach((finding) => {
        (finding.suspects || []).forEach((suspect) => {
            if (!suspect.mod) return;
            if (!byMod[suspect.mod]) byMod[suspect.mod] = new Set();
            (suspect.evidence || []).forEach((path) => byMod[suspect.mod].add(path));
        });
    });
    return Object.fromEntries(Object.entries(byMod).map(([mod, paths]) => [mod, [...paths]]));
}

export function summarizeDoctorFindingGroups(result = {}) {
    const rankedMods = asArray(result?.script_crashes?.ranked_mods);
    const uiFindings = asArray(result?.ui_crashes?.findings);
    const scriptEvidence = collectScriptEvidence(result);
    const scriptItems = rankedMods.map((item) => ({
        ...item,
        evidence: scriptEvidence[item.mod] || [],
    }));
    const errorItems = [
        ...asArray(result?.script_crashes?.parse_errors).map((message) => ({
            source: 'Script log parser',
            message,
        })),
        ...asArray(result?.ui_crashes?.parse_errors).map((message) => ({
            source: 'UI log parser',
            message,
        })),
        ...asArray(result?.ui_crashes?.index_errors).map((message) => ({
            source: 'Package index',
            message,
        })),
        ...asArray(result?.native_crashes?.parse_errors).map((message) => ({
            source: 'Native crash parser',
            message,
        })),
    ];

    return {
        needsAttention: [
            {
                label: 'Script suspects still active',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'active'),
            },
            {
                label: 'UI resources found in active packages',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'active'),
            },
        ],
        alreadyDisabled: [
            {
                label: 'Script suspects already disabled',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'disabled'),
            },
            {
                label: 'UI resources already disabled',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'disabled'),
            },
        ],
        unattributed: [
            {
                label: 'Script references not installed',
                kind: 'script',
                items: scriptItems.filter((item) => item.status === 'not_installed'),
            },
            {
                label: 'UI resources not installed',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'not_found'),
            },
            {
                label: 'UI findings without resource keys',
                kind: 'ui',
                items: uiFindings.filter((item) => item.status === 'no_key'),
            },
        ],
        errors: [
            {
                label: 'Parse and index errors',
                kind: 'error',
                items: errorItems,
            },
        ],
    };
}

export function summarizeDoctorScope(result = {}) {
    const scope = result?.evidence_scope;
    if (!scope || typeof scope !== 'object') return null;

    const counts = scope.scanned_log_counts || {};
    const archivedDisabledIncluded = Boolean(scope.archived_disabled_logs_included);
    return {
        mode: scope.mode || (archivedDisabledIncluded ? 'recursive' : 'current'),
        label: archivedDisabledIncluded ? 'Archived/quarantined included' : 'Current logs only',
        description: archivedDisabledIncluded
            ? 'Subfolders may include archived or quarantined log evidence.'
            : 'Top-level Sims 4 logs only.',
        archivedDisabledIncluded,
        counts: {
            script: count(counts.script),
            ui: count(counts.ui),
            nativeCrash: count(counts.native_crash),
        },
    };
}

export function summarizeNativeCrashes(result = {}) {
    const nativeCrashes = result?.native_crashes;
    if (!nativeCrashes || typeof nativeCrashes !== 'object') {
        return { reports: [], parseErrors: [] };
    }

    return {
        reports: asArray(nativeCrashes.reports).map((report) => {
            const sourceFile = report?.source_file || '';
            const created = report?.created || '';
            const categoryId = report?.category_id || '';
            const status = report?.status || 'unattributed_native';
            const actionability = report?.actionability || 'informational';
            return {
                id: `native-${sourceFile}-${created}-${categoryId}`,
                sourceFile,
                sourceName: basename(sourceFile),
                created,
                categoryId,
                buildSignature: report?.build_signature || '',
                modded: report?.modded ?? null,
                currentGameState: report?.current_game_state || '',
                stackSnippet: asArray(report?.stack_snippet),
                status,
                statusLabel: titleLabel(status),
                actionability,
                actionabilityLabel: titleLabel(actionability),
            };
        }),
        parseErrors: asArray(nativeCrashes.parse_errors),
    };
}

export function summarizeDoctorLedgerHistory(result = {}) {
    const history = result?.ledger_history;
    if (!history || typeof history !== 'object') return null;

    const latestScan = asArray(history.recent_scans)[0] || null;
    return {
        status: history.status || 'unknown',
        statusLabel: titleLabel(history.status),
        dbPath: history.db_path || '',
        latestScan: latestScan
            ? {
                  scanId: latestScan.scan_id ?? null,
                  scannedAt: latestScan.scanned_at || '',
                  filesTotal: count(latestScan.files_total),
                  added: count(latestScan.added),
                  moved: count(latestScan.moved),
                  modified: count(latestScan.modified),
                  removed: count(latestScan.removed),
                  unchanged: count(latestScan.unchanged),
              }
            : null,
        events: asArray(history.latest_file_events?.events).map((event) => {
            const status = event?.change_status || 'unknown';
            const path = event?.relative_path || '';
            const previousPath = event?.previous_relative_path || '';
            return {
                id: `${status}-${path}-${previousPath}`,
                path,
                status,
                statusLabel: titleLabel(status),
                previousPath,
                detail: previousPath ? `from ${previousPath}` : '',
            };
        }),
        warnings: asArray(history.warnings),
    };
}
