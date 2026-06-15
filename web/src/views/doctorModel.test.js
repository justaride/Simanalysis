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
