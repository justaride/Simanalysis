import test from 'node:test';
import assert from 'node:assert/strict';
import {
    describeRecommendation,
    recommendationActionLabel,
    summarizeMonitorEvent,
    shouldRecordMonitorEvent,
    statusText,
} from './liveMonitorModel.js';

test('waiting results are not recorded as noisy events', () => {
    assert.equal(
        shouldRecordMonitorEvent({ changed_logs: [], recommended_next_action: 'waiting' }),
        false,
    );
});

test('changed log results are recorded as events', () => {
    assert.equal(
        shouldRecordMonitorEvent({
            changed_logs: [{ name: 'lastException.txt' }],
            recommended_next_action: 'review_doctor',
        }),
        true,
    );
});

test('open treatment recommendation is primary and safe-worded', () => {
    assert.deepEqual(describeRecommendation('open_treatment'), {
        tone: 'emerald',
        title: 'Treatment has candidates to test',
        body: 'A new crash log produced active movable candidates. Open Treatment when you are ready to run a reversible test step.',
        primaryAction: 'open_treatment',
    });
});

test('unknown recommendation falls back to doctor review', () => {
    assert.deepEqual(describeRecommendation('surprise'), {
        tone: 'amber',
        title: 'Review the Doctor evidence',
        body: 'Simanalysis found evidence, but it is not safe to turn it into a Treatment action from this monitor event.',
        primaryAction: 'review_doctor',
    });
});

test('recommendation actions map to user-facing buttons', () => {
    assert.equal(recommendationActionLabel('open_treatment'), 'Open Treatment');
    assert.equal(recommendationActionLabel('review_doctor'), 'Review Doctor');
    assert.equal(recommendationActionLabel(null), null);
});

test('summarize monitor event extracts stable counts', () => {
    const summary = summarizeMonitorEvent({
        changed_logs: [{ name: 'lastUIException.txt' }],
        watched_log_count: 10,
        doctor_summary: {
            script_reports: 2,
            script_active: 1,
            ui_findings: 3,
            ui_active: 2,
        },
        treatment: {
            candidate_count: 4,
            first_batch_count: 2,
            manifest_path: null,
        },
        recommended_next_action: 'open_treatment',
    });

    assert.deepEqual(summary, {
        changedLogNames: ['lastUIException.txt'],
        watchedLogCount: 10,
        scriptReports: 2,
        scriptActive: 1,
        uiFindings: 3,
        uiActive: 2,
        candidateCount: 4,
        firstBatchCount: 2,
        manifestPath: null,
        recommendation: 'open_treatment',
        warnings: [],
        blockers: [],
    });
});

test('summarize monitor event preserves warnings and blockers', () => {
    const summary = summarizeMonitorEvent({
        changed_logs: [{ name: 'lastException.txt' }],
        warnings: ['Doctor evidence was partial'],
        treatment: {
            warnings: ['Treatment dry-run skipped one package'],
            blockers: ['No movable candidates met safety rules'],
        },
    });

    assert.deepEqual(summary.warnings, [
        'Doctor evidence was partial',
        'Treatment dry-run skipped one package',
    ]);
    assert.deepEqual(summary.blockers, ['No movable candidates met safety rules']);
});

test('status text is plain and low-jargon', () => {
    assert.equal(statusText('idle'), 'Ready to watch');
    assert.equal(statusText('watching'), 'Watching for new crash logs');
    assert.equal(statusText('event_detected'), 'New crash evidence detected');
    assert.equal(statusText('needs_review'), 'Doctor review needed');
    assert.equal(statusText('error'), 'Monitor needs attention');
    assert.equal(statusText('stopped'), 'Monitoring stopped');
});
