import React, { useState } from 'react';
import { useAppContext } from '../context/AppContext';
import api from '../api';
import { Search, FileText, Package, HardDrive, AlertCircle, CheckCircle } from 'lucide-react';

function SaveAnalyzer() {
    const { saveScanResult, isScanning, startSaveScan, completeSaveScan } = useAppContext();
    const [savePath, setSavePath] = useState('');
    const [modsPath, setModsPath] = useState('~/Documents/Electronic Arts/The Sims 4/Mods');
    const [error, setError] = useState(null);
    const [scanProgress, setScanProgress] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [showUnused, setShowUnused] = useState(false);

    const handleAnalyze = () => {
        if (!savePath.trim()) {
            setError('Please enter a save file path');
            return;
        }
        if (!modsPath.trim()) {
            setError('Please enter your Mods folder path');
            return;
        }

        setError(null);
        setScanProgress(null);
        startSaveScan();

        api.analyzeSave(savePath, modsPath, {
            onProgress: (progress) => {
                setScanProgress(progress);
            },
            onComplete: (result) => {
                completeSaveScan(result);
                setScanProgress(null);
            },
            onError: (err) => {
                setError(err);
                completeSaveScan(null);
                setScanProgress(null);
            },
        });
    };

    // Filter mods based on search term
    const filteredMods = saveScanResult
        ? (showUnused ? saveScanResult.unused_mods : saveScanResult.used_mods).filter(mod =>
            mod.name.toLowerCase().includes(searchTerm.toLowerCase())
        )
        : [];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-white mb-2">Save Analyzer</h1>
                <p className="text-gray-400">Identify which CC/mods are used in your save file</p>
            </div>

            {/* Input Section */}
            <div className="bg-gray-800 rounded-lg p-6 space-y-4">
                <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                        Save File Path
                    </label>
                    <input
                        type="text"
                        value={savePath}
                        onChange={(e) => setSavePath(e.target.value)}
                        placeholder="~/Documents/Electronic Arts/The Sims 4/saves/Slot_00000001.save"
                        className="w-full px-4 py-2 bg-gray-700 text-white rounded-md border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                        Mods Folder Path
                    </label>
                    <input
                        type="text"
                        value={modsPath}
                        onChange={(e) => setModsPath(e.target.value)}
                        placeholder="~/Documents/Electronic Arts/The Sims 4/Mods"
                        className="w-full px-4 py-2 bg-gray-700 text-white rounded-md border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                </div>

                <button
                    onClick={handleAnalyze}
                    disabled={isScanning}
                    className="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium rounded-md transition-colors"
                >
                    {isScanning ? 'Analyzing...' : 'Analyze Save'}
                </button>

                {error && <p className="text-red-500 mt-2">{error}</p>}

                {/* Progress Bar */}
                {scanProgress && (
                    <div className="mt-4">
                        <div className="flex justify-between text-sm text-gray-400 mb-1">
                            <span>{scanProgress.stage}</span>
                            <span>{Math.round((scanProgress.current / scanProgress.total) * 100)}%</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-2.5">
                            <div
                                className="bg-blue-600 h-2.5 rounded-full transition-all duration-200"
                                style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
                            ></div>
                        </div>
                        <div className="text-xs text-gray-500 mt-1 text-right">
                            {scanProgress.current} / {scanProgress.total}
                        </div>
                    </div>
                )}
            </div>

            {/* Results Section */}
            {saveScanResult && (
                <>
                    {/* Summary Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="bg-gray-800 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-gray-400 text-sm">Total Mods</p>
                                    <p className="text-2xl font-bold text-white">
                                        {saveScanResult.summary.total_mods}
                                    </p>
                                </div>
                                <Package className="text-gray-500" size={32} />
                            </div>
                        </div>

                        <div className="bg-gray-800 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-gray-400 text-sm">Used in Save</p>
                                    <p className="text-2xl font-bold text-green-400">
                                        {saveScanResult.summary.used_mods}
                                    </p>
                                </div>
                                <CheckCircle className="text-green-500" size={32} />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                {saveScanResult.summary.used_size_mb.toFixed(1)} MB
                            </p>
                        </div>

                        <div className="bg-gray-800 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-gray-400 text-sm">Unused</p>
                                    <p className="text-2xl font-bold text-yellow-400">
                                        {saveScanResult.summary.unused_mods}
                                    </p>
                                </div>
                                <AlertCircle className="text-yellow-500" size={32} />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                {saveScanResult.summary.unused_size_mb.toFixed(1)} MB
                            </p>
                        </div>

                        <div className="bg-gray-800 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-gray-400 text-sm">Coverage</p>
                                    <p className="text-2xl font-bold text-blue-400">
                                        {saveScanResult.summary.coverage_percentage}%
                                    </p>
                                </div>
                                <HardDrive className="text-blue-500" size={32} />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                {saveScanResult.summary.missing_resources} missing
                            </p>
                        </div>
                    </div>

                    {/* Mod List */}
                    <div className="bg-gray-800 rounded-lg p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-semibold text-white">
                                {showUnused ? 'Unused Mods' : 'Used Mods'}
                            </h2>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setShowUnused(false)}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${!showUnused
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                        }`}
                                >
                                    Used ({saveScanResult.summary.used_mods})
                                </button>
                                <button
                                    onClick={() => setShowUnused(true)}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${showUnused
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                        }`}
                                >
                                    Unused ({saveScanResult.summary.unused_mods})
                                </button>
                            </div>
                        </div>

                        {/* Search */}
                        <div className="relative mb-4">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                            <input
                                type="text"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                placeholder="Search mods..."
                                className="w-full pl-10 pr-4 py-2 bg-gray-700 text-white rounded-md border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>

                        {/* Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-gray-700">
                                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Name</th>
                                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Resources</th>
                                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Size</th>
                                        {!showUnused && (
                                            <th className="text-left py-3 px-4 text-gray-400 font-medium">Used</th>
                                        )}
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredMods.length > 0 ? (
                                        filteredMods.map((mod, idx) => (
                                            <tr key={idx} className="border-b border-gray-700 hover:bg-gray-750">
                                                <td className="py-3 px-4 text-white">{mod.name}</td>
                                                <td className="py-3 px-4 text-gray-300">{mod.resource_count}</td>
                                                <td className="py-3 px-4 text-gray-300">
                                                    {(mod.size / 1024 / 1024).toFixed(2)} MB
                                                </td>
                                                {!showUnused && (
                                                    <td className="py-3 px-4 text-gray-300">
                                                        {mod.matching_resources || 0} items
                                                    </td>
                                                )}
                                            </tr>
                                        ))
                                    ) : (
                                        <tr>
                                            <td colSpan="4" className="py-8 px-4 text-center text-gray-500">
                                                No mods found
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {/* Empty State */}
            {!saveScanResult && !isScanning && (
                <div className="bg-gray-800 rounded-lg p-12 text-center">
                    <FileText className="mx-auto mb-4 text-gray-600" size={64} />
                    <h3 className="text-xl font-semibold text-white mb-2">No Analysis Yet</h3>
                    <p className="text-gray-400">
                        Enter your save file and Mods folder paths above to analyze which CC is used
                    </p>
                </div>
            )}
        </div>
    );
}

export default SaveAnalyzer;
