const RECOMMENDATIONS = {
    open_treatment: {
        tone: 'emerald',
        title: 'Treatment has candidates to test',
        body: 'A new crash log produced active movable candidates. Open Treatment when you are ready to run a reversible test step.',
        primaryAction: 'open_treatment',
    },
    review_doctor: {
        tone: 'amber',
        title: 'Review the Doctor evidence',
        body: 'Simanalysis found evidence, but it is not safe to turn it into a Treatment action from this monitor event.',
        primaryAction: 'review_doctor',
    },
    no_movable_candidates: {
        tone: 'blue',
        title: 'No movable candidates',
        body: 'The new evidence does not point at anything Simanalysis can safely move. Keep the log for review.',
        primaryAction: null,
    },
    waiting: {
        tone: 'gray',
        title: 'Waiting for a new crash log',
        body: 'No new crash evidence has appeared since monitoring started.',
        primaryAction: null,
    },
};

const STATUS_TEXT = {
    idle: 'Ready to watch',
    watching: 'Watching for new crash logs',
    event_detected: 'New crash evidence detected',
    needs_review: 'Doctor review needed',
    error: 'Monitor needs attention',
    stopped: 'Monitoring stopped',
};

export function describeRecommendation(action) {
    return RECOMMENDATIONS[action] || RECOMMENDATIONS.review_doctor;
}

export function recommendationActionLabel(primaryAction) {
    return {
        open_treatment: 'Open Treatment',
        review_doctor: 'Review Doctor',
    }[primaryAction] || null;
}

export function shouldRecordMonitorEvent(data) {
    return (data?.changed_logs || []).length > 0;
}

export function summarizeMonitorEvent(data = {}) {
    const doctor = data.doctor_summary || {};
    const treatment = data.treatment || {};
    const warnings = [
        ...(data.warnings || []),
        ...(treatment.warnings || []),
    ];
    return {
        changedLogNames: (data.changed_logs || []).map((log) => log.name || log.path || 'crash log'),
        watchedLogCount: data.watched_log_count || 0,
        scriptReports: doctor.script_reports || 0,
        scriptActive: doctor.script_active || 0,
        uiFindings: doctor.ui_findings || 0,
        uiActive: doctor.ui_active || 0,
        candidateCount: treatment.candidate_count || 0,
        firstBatchCount: treatment.first_batch_count || 0,
        manifestPath: treatment.manifest_path || null,
        recommendation: data.recommended_next_action || 'waiting',
        warnings,
        blockers: treatment.blockers || [],
    };
}

export function statusText(status) {
    return STATUS_TEXT[status] || STATUS_TEXT.idle;
}
