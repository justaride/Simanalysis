import assert from 'node:assert/strict';
import test from 'node:test';

import {
    canRequestTreatmentHandoff,
    summarizeTreatmentHandoff,
    treatmentHandoffFilename,
} from './treatmentModel.js';

test('handoff can only be requested for a saved Treatment session', () => {
    assert.equal(canRequestTreatmentHandoff(null), false);
    assert.equal(canRequestTreatmentHandoff({ manifest_path: null }), false);
    assert.equal(canRequestTreatmentHandoff({ manifest_path: '/Sims/_Simanalysis_Treatment/bisect-test.json' }), true);
});

test('handoff summary extracts the markdown contract from bridge payload', () => {
    const summary = summarizeTreatmentHandoff({
        manifest_path: '/Sims/_Simanalysis_Treatment/bisect-test.json',
        handoff: '# Simanalysis Bisect Handoff\n\nManifest: `/Sims/_Simanalysis_Treatment/bisect-test.json`\n',
        session: {
            status: 'awaiting_result',
            session_id: 'bisect-test',
        },
    });

    assert.deepEqual(summary, {
        manifestPath: '/Sims/_Simanalysis_Treatment/bisect-test.json',
        markdown: '# Simanalysis Bisect Handoff\n\nManifest: `/Sims/_Simanalysis_Treatment/bisect-test.json`\n',
        title: 'Simanalysis Bisect Handoff',
        lineCount: 3,
        sessionId: 'bisect-test',
        status: 'awaiting_result',
    });
});

test('handoff summary falls back without overstating missing data', () => {
    assert.deepEqual(summarizeTreatmentHandoff({}), {
        manifestPath: null,
        markdown: '',
        title: 'Treatment handoff',
        lineCount: 0,
        sessionId: null,
        status: null,
    });
});

test('handoff download filename is derived from the manifest basename', () => {
    assert.equal(
        treatmentHandoffFilename('/Sims/_Simanalysis_Treatment/bisect test.json'),
        'simanalysis-bisect-handoff-bisect-test.md',
    );
    assert.equal(treatmentHandoffFilename(''), 'simanalysis-bisect-handoff-session.md');
});
