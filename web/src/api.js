const API_BASE = '/api';

export const api = {
    health: async () => {
        const res = await fetch(`${API_BASE}/health`);
        return res.json();
    },

    scanMods: (path, callbacks) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${API_BASE}/ws/scan`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            ws.send(JSON.stringify({ path, recursive: true, quick: false }));
            callbacks?.onStart?.();
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status === 'scanning') {
                callbacks?.onProgress?.({
                    current: data.current,
                    total: data.total,
                    file: data.file,
                });
            } else if (data.status === 'complete') {
                callbacks?.onComplete?.(data.result);
                ws.close();
            } else if (data.status === 'error') {
                callbacks?.onError?.(data.message);
                ws.close();
            }
        };

        ws.onerror = () => {
            callbacks?.onError?.('Connection failed. Is the backend running?');
        };

        return ws;
    },

    scanTray: (path, callbacks) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${API_BASE}/ws/scan/tray`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            ws.send(JSON.stringify({ path }));
            callbacks?.onStart?.();
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status === 'scanning') {
                callbacks?.onProgress?.({
                    current: data.current,
                    total: data.total,
                    file: data.file,
                });
            } else if (data.status === 'complete') {
                callbacks?.onComplete?.(data.result);
                ws.close();
            } else if (data.status === 'error') {
                callbacks?.onError?.(data.message);
                ws.close();
            }
        };

        ws.onerror = () => {
            callbacks?.onError?.('Connection failed. Is the backend running?');
        };

        return ws;
    },

    analyzeSave: (savePath, modsPath, callbacks) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${API_BASE}/ws/analyze/save`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            ws.send(JSON.stringify({ save_path: savePath, mods_path: modsPath }));
            callbacks?.onStart?.();
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status === 'analyzing') {
                callbacks?.onProgress?.({
                    stage: data.stage,
                    current: data.current,
                    total: data.total,
                });
            } else if (data.status === 'complete') {
                callbacks?.onComplete?.(data.result);
                ws.close();
            } else if (data.status === 'error') {
                callbacks?.onError?.(data.message);
                ws.close();
            }
        };

        ws.onerror = () => {
            callbacks?.onError?.('Connection failed. Is the backend running?');
        };

        return ws;
    },
};

export default api;
