import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import api from '../api';
import { useProfileDefaultPath } from '../hooks/useProfileDefaultPath';
import { shouldRecordMonitorEvent } from '../views/liveMonitorModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';
const DEFAULT_INTERVAL = 2;

const LiveMonitorContext = createContext(null);

function nextStatusFromResult(data) {
    if (data?.recommended_next_action === 'review_doctor') return 'needs_review';
    if ((data?.changed_logs || []).length > 0) return 'event_detected';
    return 'watching';
}

export function LiveMonitorProvider({ children }) {
    const handleRef = useRef(null);
    const runIdRef = useRef(0);
    const [simsPath, setSimsPath] = useProfileDefaultPath('simsPath', {
        fallback: DEFAULT_SIMS_PATH,
    });
    const [modsPath, setModsPath] = useProfileDefaultPath('modsPath');
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [latestEvent, setLatestEvent] = useState(null);
    const [history, setHistory] = useState([]);
    const [error, setError] = useState(null);

    const stop = useCallback(() => {
        runIdRef.current += 1;
        handleRef.current?.cancel?.();
        handleRef.current = null;
        setProgress(null);
        setStatus('stopped');
    }, []);

    const start = useCallback(() => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            setStatus('error');
            return;
        }

        runIdRef.current += 1;
        const runId = runIdRef.current;
        handleRef.current?.cancel?.();
        setError(null);
        setProgress(null);
        setLatestEvent(null);
        setHistory([]);
        setStatus('watching');

        handleRef.current = api.monitorLive(simsPath.trim(), modsPath.trim() || null, DEFAULT_INTERVAL, {
            onStart: () => {
                if (runIdRef.current !== runId) return;
                setStatus('watching');
            },
            onProgress: (nextProgress) => {
                if (runIdRef.current !== runId) return;
                setProgress(nextProgress);
                setStatus((current) => (current === 'error' ? current : 'watching'));
            },
            onResult: (data) => {
                if (runIdRef.current !== runId) return;
                setProgress(null);
                setStatus(nextStatusFromResult(data));
                if (!shouldRecordMonitorEvent(data)) return;
                const event = {
                    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                    receivedAt: new Date().toISOString(),
                    data,
                };
                setLatestEvent(event);
                setHistory((items) => [event, ...items].slice(0, 20));
            },
            onError: (message) => {
                if (runIdRef.current !== runId) return;
                setError(message);
                setProgress(null);
                setStatus('error');
                handleRef.current = null;
            },
            onDone: () => {
                if (runIdRef.current !== runId) return;
                handleRef.current = null;
                setProgress(null);
                setStatus((current) => (current === 'error' ? current : 'stopped'));
            },
        });
    }, [modsPath, simsPath]);

    useEffect(() => () => {
        runIdRef.current += 1;
        handleRef.current?.cancel?.();
        handleRef.current = null;
    }, []);

    const isWatching = status === 'watching' || status === 'event_detected' || status === 'needs_review';

    return (
        <LiveMonitorContext.Provider
            value={{
                simsPath,
                setSimsPath,
                modsPath,
                setModsPath,
                status,
                progress,
                latestEvent,
                history,
                error,
                isWatching,
                start,
                stop,
            }}
        >
            {children}
        </LiveMonitorContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLiveMonitor() {
    const context = useContext(LiveMonitorContext);
    if (!context) {
        throw new Error('useLiveMonitor must be used within LiveMonitorProvider');
    }
    return context;
}
