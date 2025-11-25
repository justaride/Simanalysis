import { createContext, useContext, useState, useCallback } from 'react';

const AppContext = createContext(null);

export function AppProvider({ children }) {
    const [modScanResult, setModScanResult] = useState(null);
    const [trayScanResult, setTrayScanResult] = useState(null);
    const [saveScanResult, setSaveScanResult] = useState(null);
    const [isScanning, setIsScanning] = useState(false);
    const [scanProgress, setScanProgress] = useState(null);

    const startModScan = useCallback((path) => {
        setIsScanning(true);
        setScanProgress({ current: 0, total: 0, file: '' });
        setModScanResult(null);
    }, []);

    const updateModScanProgress = useCallback((progress) => {
        setScanProgress(progress);
    }, []);

    const completeModScan = useCallback((result) => {
        setModScanResult(result);
        setIsScanning(false);
        setScanProgress(null);
    }, []);

    const startTrayScan = useCallback((path) => {
        setIsScanning(true);
        setTrayScanResult(null);
    }, []);

    const completeTrayScan = useCallback((result) => {
        setTrayScanResult(result);
        setIsScanning(false);
    }, []);

    const startSaveScan = useCallback(() => {
        setIsScanning(true);
        setSaveScanResult(null);
    }, []);

    const completeSaveScan = useCallback((result) => {
        setSaveScanResult(result);
        setIsScanning(false);
    }, []);

    const resetScans = useCallback(() => {
        setModScanResult(null);
        setTrayScanResult(null);
        setSaveScanResult(null);
        setIsScanning(false);
        setScanProgress(null);
    }, []);

    return (
        <AppContext.Provider
            value={{
                modScanResult,
                trayScanResult,
                saveScanResult,
                isScanning,
                scanProgress,
                startModScan,
                updateModScanProgress,
                completeModScan,
                startTrayScan,
                completeTrayScan,
                startSaveScan,
                completeSaveScan,
                resetScans,
            }}
        >
            {children}
        </AppContext.Provider>
    );
}

export function useAppContext() {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error('useAppContext must be used within AppProvider');
    }
    return context;
}
