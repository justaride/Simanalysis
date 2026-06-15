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
