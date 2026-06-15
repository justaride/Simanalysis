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
