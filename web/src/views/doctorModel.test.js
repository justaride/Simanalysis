import assert from 'node:assert/strict';
import test from 'node:test';

async function loadModel() {
    return import('./doctorModel.js');
}

test('doctor verdict rows preserve evidence and labels next actions', async () => {
    const { summarizeDoctorVerdicts } = await loadModel();
    const rows = summarizeDoctorVerdicts({
        verdicts: [
            {
                id: 'active-script-suspects',
                status: 'needs_action',
                severity: 'high',
                title: 'Active script suspects found',
                recommended_next_action: 'start_bisect',
                confidence: 'direct',
                evidence: [
                    { label: 'Active script suspects', value: 1 },
                    { label: 'Script crash reports', value: 2 },
                ],
            },
        ],
    });

    assert.deepEqual(rows, [
        {
            id: 'active-script-suspects',
            title: 'Active script suspects found',
            status: 'needs_action',
            statusLabel: 'Needs action',
            severity: 'high',
            severityLabel: 'High',
            confidence: 'direct',
            confidenceLabel: 'Direct',
            nextAction: 'start_bisect',
            nextActionLabel: 'Start Bisect',
            tone: 'red',
            evidence: ['Active script suspects: 1', 'Script crash reports: 2'],
        },
    ]);
});

test('doctor verdict rows stay honest when payload omits verdicts', async () => {
    const { summarizeDoctorVerdicts } = await loadModel();

    assert.deepEqual(summarizeDoctorVerdicts({ summary: { script_active: 1 } }), []);
    assert.deepEqual(summarizeDoctorVerdicts(null), []);
});

test('doctor playbook rows expose command, requirements, and availability', async () => {
    const { summarizeDoctorPlaybooks } = await loadModel();
    const rows = summarizeDoctorPlaybooks({
        playbooks: [
            {
                id: 'bisect-active-doctor-candidates',
                title: 'Start bisection from Doctor JSON',
                symptom: 'active_crash_candidates',
                available: true,
                next_command: 'simanalysis bisect start <The Sims 4> --doctor-json <doctor.json>',
                requires: ['saved Doctor JSON', 'manifest-based bisection session'],
                reason: 'Active Doctor candidates are present.',
            },
        ],
    });

    assert.deepEqual(rows, [
        {
            id: 'bisect-active-doctor-candidates',
            title: 'Start bisection from Doctor JSON',
            symptom: 'Active crash candidates',
            available: true,
            nextCommand: 'simanalysis bisect start <The Sims 4> --doctor-json <doctor.json>',
            requires: ['saved Doctor JSON', 'manifest-based bisection session'],
            reason: 'Active Doctor candidates are present.',
        },
    ]);
});

test('doctor playbook rows stay empty without backend playbooks', async () => {
    const { summarizeDoctorPlaybooks } = await loadModel();

    assert.deepEqual(summarizeDoctorPlaybooks({ playbooks: null }), []);
    assert.deepEqual(summarizeDoctorPlaybooks(undefined), []);
});

test('doctor timeline rows preserve chronological evidence labels', async () => {
    const { summarizeDoctorTimeline } = await loadModel();
    const rows = summarizeDoctorTimeline({
        timeline: [
            {
                kind: 'script',
                created: '2026-06-14T20:00:00Z',
                source_file: '/Sims/The Sims 4/lastException_old.txt',
                message: 'Older script failure',
            },
            {
                kind: 'ui',
                created: '2026-06-15T00:30:00Z',
                source_file: '/Sims/The Sims 4/lastUIException.txt',
                message: 'BuildBuy03B',
            },
        ],
    });

    assert.deepEqual(rows, [
        {
            id: 'script-2026-06-14T20:00:00Z-/Sims/The Sims 4/lastException_old.txt',
            kind: 'script',
            kindLabel: 'Script',
            created: '2026-06-14T20:00:00Z',
            sourceFile: '/Sims/The Sims 4/lastException_old.txt',
            sourceName: 'lastException_old.txt',
            message: 'Older script failure',
        },
        {
            id: 'ui-2026-06-15T00:30:00Z-/Sims/The Sims 4/lastUIException.txt',
            kind: 'ui',
            kindLabel: 'UI',
            created: '2026-06-15T00:30:00Z',
            sourceFile: '/Sims/The Sims 4/lastUIException.txt',
            sourceName: 'lastUIException.txt',
            message: 'BuildBuy03B',
        },
    ]);
});

test('doctor scope summary labels current and recursive evidence', async () => {
    const { summarizeDoctorScope } = await loadModel();

    assert.deepEqual(
        summarizeDoctorScope({
            evidence_scope: {
                mode: 'current',
                archived_disabled_logs_included: false,
                scanned_log_counts: { script: 1, ui: 0, native_crash: 1 },
            },
        }),
        {
            mode: 'current',
            label: 'Current logs only',
            description: 'Top-level Sims 4 logs only.',
            archivedDisabledIncluded: false,
            counts: { script: 1, ui: 0, nativeCrash: 1 },
        },
    );

    assert.deepEqual(
        summarizeDoctorScope({
            evidence_scope: {
                mode: 'recursive',
                archived_disabled_logs_included: true,
                scanned_log_counts: { script: 2, ui: 1, native_crash: 3 },
            },
        }),
        {
            mode: 'recursive',
            label: 'Archived/quarantined included',
            description: 'Subfolders may include archived or quarantined log evidence.',
            archivedDisabledIncluded: true,
            counts: { script: 2, ui: 1, nativeCrash: 3 },
        },
    );
});

test('doctor native crash summaries render as unattributed evidence', async () => {
    const { summarizeNativeCrashes } = await loadModel();

    assert.deepEqual(
        summarizeNativeCrashes({
            native_crashes: {
                reports: [
                    {
                        source_file: '/Sims/The Sims 4/lastCrash.txt',
                        created: '2026-06-16 22:19:10',
                        category_id: 'gameplay.NativeCrash',
                        build_signature: 'Local.1.124.55.1230',
                        modded: false,
                        current_game_state: 'Live_Mode',
                        stack_snippet: ['Native stack line'],
                        status: 'unattributed_native',
                        actionability: 'informational',
                    },
                ],
                parse_errors: ['lastCrash_bad.txt: unterminated <report>'],
            },
        }),
        {
            reports: [
                {
                    id: 'native-/Sims/The Sims 4/lastCrash.txt-2026-06-16 22:19:10-gameplay.NativeCrash',
                    sourceFile: '/Sims/The Sims 4/lastCrash.txt',
                    sourceName: 'lastCrash.txt',
                    created: '2026-06-16 22:19:10',
                    categoryId: 'gameplay.NativeCrash',
                    buildSignature: 'Local.1.124.55.1230',
                    modded: false,
                    currentGameState: 'Live_Mode',
                    stackSnippet: ['Native stack line'],
                    status: 'unattributed_native',
                    statusLabel: 'Unattributed native',
                    actionability: 'informational',
                    actionabilityLabel: 'Informational',
                },
            ],
            parseErrors: ['lastCrash_bad.txt: unterminated <report>'],
        },
    );
});

test('doctor finding groups separate no-key UI evidence from package matches', async () => {
    const { summarizeDoctorFindingGroups } = await loadModel();
    const groups = summarizeDoctorFindingGroups({
        script_crashes: {
            ranked_mods: [{ mod: 'Missing.ts4script', status: 'not_installed' }],
            findings: [],
            parse_errors: [],
        },
        ui_crashes: {
            findings: [
                {
                    status: 'active',
                    report: { signature: 'active', message: 'Active package hit' },
                    hits: [{ status: 'active', package_name: 'menu.package' }],
                },
                {
                    status: 'no_key',
                    report: { signature: 'nokey', message: 'No resource key' },
                    hits: [],
                },
                {
                    status: 'not_found',
                    report: { signature: 'missing', message: 'Missing package' },
                    hits: [],
                },
            ],
            parse_errors: [],
            index_errors: [],
        },
    });

    assert.equal(groups.needsAttention[1].items.length, 1);
    assert.deepEqual(
        groups.unattributed.map((group) => [group.label, group.items.length]),
        [
            ['Script references not installed', 1],
            ['UI resources not installed', 1],
            ['UI findings without resource keys', 1],
        ],
    );
});

test('doctor ledger history summarizes scans and latest file events', async () => {
    const { summarizeDoctorLedgerHistory } = await loadModel();
    const summary = summarizeDoctorLedgerHistory({
        ledger_history: {
            status: 'available',
            db_path: '/Sims/inventory.sqlite3',
            recent_scans: [
                {
                    scan_id: 7,
                    scanned_at: '2026-06-15T01:00:00Z',
                    files_total: 42,
                    added: 1,
                    moved: 1,
                    modified: 2,
                    removed: 0,
                    unchanged: 38,
                },
            ],
            latest_file_events: {
                events: [
                    {
                        relative_path: 'Mods/Moved/Alpha.package',
                        change_status: 'moved',
                        previous_relative_path: 'Mods/Alpha.package',
                    },
                    {
                        relative_path: 'lastException.txt',
                        change_status: 'added',
                    },
                ],
            },
            warnings: ['Ledger snapshot is older than latest crash log.'],
        },
    });

    assert.deepEqual(summary, {
        status: 'available',
        statusLabel: 'Available',
        dbPath: '/Sims/inventory.sqlite3',
        latestScan: {
            scanId: 7,
            scannedAt: '2026-06-15T01:00:00Z',
            filesTotal: 42,
            added: 1,
            moved: 1,
            modified: 2,
            removed: 0,
            unchanged: 38,
        },
        events: [
            {
                id: 'moved-Mods/Moved/Alpha.package-Mods/Alpha.package',
                path: 'Mods/Moved/Alpha.package',
                status: 'moved',
                statusLabel: 'Moved',
                previousPath: 'Mods/Alpha.package',
                detail: 'from Mods/Alpha.package',
            },
            {
                id: 'added-lastException.txt-',
                path: 'lastException.txt',
                status: 'added',
                statusLabel: 'Added',
                previousPath: '',
                detail: '',
            },
        ],
        warnings: ['Ledger snapshot is older than latest crash log.'],
    });
});

test('doctor timeline and ledger models stay empty without backend evidence', async () => {
    const { summarizeDoctorLedgerHistory, summarizeDoctorTimeline } = await loadModel();

    assert.deepEqual(summarizeDoctorTimeline({}), []);
    assert.equal(summarizeDoctorLedgerHistory({}), null);
});
