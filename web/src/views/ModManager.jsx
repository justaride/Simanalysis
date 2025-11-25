import { useState } from 'react';
import { Search, Filter, Download, Loader2 } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';

function ModManager() {
    const { modScanResult, isScanning, scanProgress, startModScan, updateModScanProgress, completeModScan } = useAppContext();
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('all');
    const [scanPath, setScanPath] = useState('');
    const [error, setError] = useState(null);

    const handleScan = () => {
        if (!scanPath.trim()) {
            setError('Please enter a path');
            return;
        }

        setError(null);
        startModScan(scanPath);

        api.scanMods(scanPath, {
            onProgress: (progress) => {
                updateModScanProgress(progress);
            },
            onComplete: (result) => {
                completeModScan(result);
            },
            onError: (err) => {
                setError(err);
                completeModScan(null);
            },
        });
    };

    // Transform mods from scan result
    const mods = modScanResult?.summary?.scan_summary?.mods_scanned
        ? Array.from({ length: modScanResult.summary.scan_summary.mods_scanned }, (_, i) => ({
            id: i,
            name: `Mod ${i + 1}`,
            type: 'Package',
            size: '1.2 MB',
            author: 'Unknown',
            date: '2024-01-01',
            conflicts: 0,
        }))
        : [];

    const filteredMods = mods.filter((mod) => {
        const matchesSearch = mod.name.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesFilter = filterType === 'all' || mod.type.toLowerCase() === filterType;
        return matchesSearch && matchesFilter;
    });

    return (
        <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Mod Manager</h1>
                <p className="text-gray-400 mt-1">View and manage your installed mods</p>
            </div>

            {/* Scan Input */}
            <div className="bg-gray-800 p-6 rounded-xl mb-6">
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="/path/to/Mods"
                        value={scanPath}
                        onChange={(e) => setScanPath(e.target.value)}
                        className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                    <button
                        onClick={handleScan}
                        disabled={isScanning}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-2 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        {isScanning ? (
                            <>
                                <Loader2 size={20} className="animate-spin" />
                                <span>Scanning...</span>
                            </>
                        ) : (
                            <>
                                <Download size={20} />
                                <span>Scan Folder</span>
                            </>
                        )}
                    </button>
                </div>
                {error && <p className="text-red-500 mt-2">{error}</p>}

                {/* Progress */}
                {scanProgress && (
                    <div className="mt-4">
                        <div className="flex justify-between text-sm text-gray-400 mb-1">
                            <span>Scanning: {scanProgress.file}</span>
                            <span>{Math.round((scanProgress.current / scanProgress.total) * 100)}%</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-2.5">
                            <div
                                className="bg-blue-600 h-2.5 rounded-full transition-all duration-200"
                                style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
                            ></div>
                        </div>
                    </div>
                )}
            </div>

            {modScanResult && (
                <>
                    {/* Toolbar */}
                    <div className="bg-gray-800 p-4 rounded-xl mb-6 flex gap-4 items-center">
                        {/* Search */}
                        <div className="flex-1 relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                            <input
                                type="text"
                                placeholder="Search mods..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full bg-gray-700 text-white px-10 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                            />
                        </div>

                        {/* Filter */}
                        <div className="flex items-center gap-2">
                            <Filter size={20} className="text-gray-400" />
                            <select
                                value={filterType}
                                onChange={(e) => setFilterType(e.target.value)}
                                className="bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                            >
                                <option value="all">All Types</option>
                                <option value="script">Scripts</option>
                                <option value="package">Packages</option>
                            </select>
                        </div>
                    </div>

                    {/* Results Summary */}
                    <div className="bg-blue-900/20 border border-blue-500 p-4 rounded-xl mb-6">
                        <p className="text-blue-200">
                            <strong>Scan Complete!</strong> Found {modScanResult.summary.total_mods} mods with{' '}
                            {modScanResult.summary.total_conflicts} conflicts.
                        </p>
                    </div>

                    {/* Table */}
                    <div className="bg-gray-800 rounded-xl overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-gray-700">
                                <tr>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Name</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Type</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Size</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Author</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Date</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-700">
                                {filteredMods.map((mod) => (
                                    <tr key={mod.id} className="hover:bg-gray-750 transition-colors">
                                        <td className="px-6 py-4 text-white font-medium">{mod.name}</td>
                                        <td className="px-6 py-4">
                                            <span
                                                className={`px-3 py-1 rounded-full text-xs font-medium ${mod.type === 'Script'
                                                        ? 'bg-purple-900 text-purple-200'
                                                        : 'bg-blue-900 text-blue-200'
                                                    }`}
                                            >
                                                {mod.type}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-gray-300">{mod.size}</td>
                                        <td className="px-6 py-4 text-gray-300">{mod.author}</td>
                                        <td className="px-6 py-4 text-gray-400 text-sm">{mod.date}</td>
                                        <td className="px-6 py-4">
                                            {mod.conflicts > 0 ? (
                                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-900 text-red-200">
                                                    {mod.conflicts} Conflict{mod.conflicts > 1 ? 's' : ''}
                                                </span>
                                            ) : (
                                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-900 text-green-200">
                                                    OK
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        {filteredMods.length === 0 && (
                            <div className="p-12 text-center text-gray-400">
                                <p>No mods found matching your criteria</p>
                            </div>
                        )}
                    </div>
                </>
            )}

            {!modScanResult && !isScanning && (
                <div className="bg-gray-800 rounded-xl p-12 text-center text-gray-400">
                    <Download size={64} className="mx-auto mb-4 opacity-50" />
                    <h3 className="text-xl font-bold text-white mb-2">No Scan Results</h3>
                    <p>Enter a path and click "Scan Folder" to analyze your mods</p>
                </div>
            )}
        </div>
    );
}

export default ModManager;
