import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import api from '../api';
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
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [modsPath, setModsPath] = useState('');
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [latestEvent, setLatestEvent] = useState(null);
    const [history, setHistory] = useState([]);
    const [error, setError] = useState(null);

    const stop = useCallback(() => {
        handleRef.current?.cancel?.();
        handleRef.current = null;
        setStatus('stopped');
    }, []);

    const start = useCallback(() => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            setStatus('error');
            return;
        }

        handleRef.current?.cancel?.();
        setError(null);
        setProgress(null);
        setLatestEvent(null);
        setHistory([]);
        setStatus('watching');

        handleRef.current = api.monitorLive(simsPath.trim(), modsPath.trim() || null, DEFAULT_INTERVAL, {
            onStart: () => setStatus('watching'),
            onProgress: (nextProgress) => {
                setProgress(nextProgress);
                setStatus((current) => (current === 'error' ? current : 'watching'));
            },
            onResult: (data) => {
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
                setError(message);
                setProgress(null);
                setStatus('error');
                handleRef.current = null;
            },
            onDone: () => {
                handleRef.current = null;
                setStatus((current) => (current === 'error' ? current : 'stopped'));
            },
        });
    }, [modsPath, simsPath]);

    useEffect(() => () => {
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
