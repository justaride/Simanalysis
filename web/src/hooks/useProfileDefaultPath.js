import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import {
    chooseProfileDefaultPath,
    profileDefaultsFromConfig,
} from '../views/settingsModel';

function readStoredPath(storageKey) {
    if (!storageKey || typeof localStorage === 'undefined') return '';
    return localStorage.getItem(storageKey) || '';
}

export function useProfileDefaultPath(defaultKey, { storageKey, fallback = '', preserveFallback = false } = {}) {
    const fallbackPath = chooseProfileDefaultPath({}, defaultKey, '', fallback);
    const [path, setPath] = useState(() => chooseProfileDefaultPath({}, defaultKey, readStoredPath(storageKey), fallback));

    useEffect(() => {
        const stored = readStoredPath(storageKey);
        if (stored) {
            setPath((current) => current || stored);
            return undefined;
        }

        let cancelled = false;
        invoke('get_config')
            .then((config) => {
                if (cancelled) return;
                const defaults = profileDefaultsFromConfig(config);
                const nextPath = chooseProfileDefaultPath(defaults, defaultKey, '', fallback);
                if (nextPath) {
                    setPath((current) => {
                        if (!current) return nextPath;
                        if (!preserveFallback && current === fallbackPath) return nextPath;
                        return current;
                    });
                }
            })
            .catch(() => {
                // Non-Tauri browser sessions keep the fallback value.
            });

        return () => {
            cancelled = true;
        };
    }, [defaultKey, fallback, fallbackPath, preserveFallback, storageKey]);

    return [path, setPath];
}
