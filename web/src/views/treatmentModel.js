function manifestBasename(manifestPath) {
    const raw = String(manifestPath || '').trim();
    if (!raw) return 'session';

    const basename = raw.split(/[\\/]/).filter(Boolean).pop() || 'session';
    const withoutExtension = basename.replace(/\.[^.]+$/, '');
    const slug = withoutExtension
        .replace(/[^A-Za-z0-9._-]+/g, '-')
        .replace(/^-+|-+$/g, '');

    return slug || 'session';
}

export function canRequestTreatmentHandoff(result) {
    return Boolean(result?.manifest_path);
}

export function summarizeTreatmentHandoff(payload = {}) {
    const markdown = typeof payload.handoff === 'string' ? payload.handoff : '';
    const lines = markdown.trimEnd() ? markdown.trimEnd().split(/\r\n|\r|\n/) : [];
    const heading = lines.find((line) => line.trim().startsWith('# '));
    const session = payload.session || {};

    return {
        manifestPath: payload.manifest_path || null,
        markdown,
        title: heading ? heading.replace(/^#+\s*/, '').trim() : 'Treatment handoff',
        lineCount: lines.length,
        sessionId: session.session_id || session.operation_id || null,
        status: session.status || null,
    };
}

export function treatmentHandoffFilename(manifestPath) {
    return `simanalysis-bisect-handoff-${manifestBasename(manifestPath)}.md`;
}
