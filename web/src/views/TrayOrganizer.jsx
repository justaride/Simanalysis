import { useState } from 'react';
import { Grid, List, Search, Download, Loader2 } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';

function TrayOrganizer() {
    const { trayScanResult, isScanning, startTrayScan, completeTrayScan } = useAppContext();
    const [viewMode, setViewMode] = useState('grid');
    const [searchTerm, setSearchTerm] = useState('');
    const [scanPath, setScanPath] = useState('');
    const [error, setError] = useState(null);
    const [scanProgress, setScanProgress] = useState(null);

    const handleScan = () => {
        if (!scanPath.trim()) {
            setError('Please enter a path');
            return;
        }

        setError(null);
        setScanProgress(null);
        startTrayScan(scanPath);

        api.scanTray(scanPath, {
            onProgress: (progress) => {
                setScanProgress(progress);
            },
            onComplete: (result) => {
                completeTrayScan(result);
                setScanProgress(null);
            },
            onError: (err) => {
                setError(err);
                completeTrayScan(null);
                setScanProgress(null);
            },
        });
    };

    const trayItems = trayScanResult?.items || [];

    const filteredItems = trayItems.filter((item) =>
        item.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Tray Organizer</h1>
                <p className="text-gray-400 mt-1">Manage your households and lots</p>
            </div>

            {/* Scan Input */}
            <div className="bg-gray-800 p-6 rounded-xl mb-6">
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="/path/to/Tray"
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

                {/* Progress Bar */}
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
                        <div className="text-xs text-gray-500 mt-1 text-right">
                            {scanProgress.current} / {scanProgress.total} files
                        </div>
                    </div>
                )}
            </div>

            {trayScanResult && (
                <>
                    {/* Toolbar */}
                    <div className="bg-gray-800 p-4 rounded-xl mb-6 flex gap-4 items-center">
                        {/* Search */}
                        <div className="flex-1 relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                            <input
                                type="text"
                                placeholder="Search tray items..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full bg-gray-700 text-white px-10 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                            />
                        </div>

                        {/* View Toggle */}
                        <div className="flex bg-gray-700 rounded-lg p-1">
                            <button
                                onClick={() => setViewMode('grid')}
                                className={`p-2 rounded ${viewMode === 'grid' ? 'bg-blue-600 text-white' : 'text-gray-400'
                                    } transition-colors`}
                            >
                                <Grid size={20} />
                            </button>
                            <button
                                onClick={() => setViewMode('list')}
                                className={`p-2 rounded ${viewMode === 'list' ? 'bg-blue-600 text-white' : 'text-gray-400'
                                    } transition-colors`}
                            >
                                <List size={20} />
                            </button>
                        </div>
                    </div>

                    {/* Results Summary */}
                    <div className="bg-blue-900/20 border border-blue-500 p-4 rounded-xl mb-6">
                        <p className="text-blue-200">
                            <strong>Scan Complete!</strong> Found {trayScanResult.summary.total_items} tray items (
                            {trayScanResult.summary.households} households, {trayScanResult.summary.lots_rooms} lots/rooms).
                        </p>
                    </div>

                    {/* Grid View */}
                    {viewMode === 'grid' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                            {filteredItems.map((item, idx) => (
                                <div
                                    key={idx}
                                    className="bg-gray-800 rounded-xl overflow-hidden hover:ring-2 hover:ring-blue-500 transition-all cursor-pointer group"
                                >
                                    {/* Thumbnail placeholder */}
                                    <div className="h-48 bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
                                        <span className="text-6xl">{item.type === 'Household' ? '👨‍👩‍👧‍👦' : '🏠'}</span>
                                    </div>

                                    {/* Details */}
                                    <div className="p-4">
                                        <h3 className="font-bold text-white text-lg mb-1">{item.name}</h3>
                                        <span
                                            className={`px-2 py-1 rounded-full text-xs font-medium ${item.type === 'Household'
                                                ? 'bg-green-900 text-green-200'
                                                : 'bg-purple-900 text-purple-200'
                                                } inline-block mb-2`}
                                        >
                                            {item.type}
                                        </span>
                                        <div className="text-sm text-gray-400 space-y-1">
                                            <p>{item.file_count} files • {(item.size / 1024).toFixed(1)} KB</p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* List View */}
                    {viewMode === 'list' && (
                        <div className="bg-gray-800 rounded-xl overflow-hidden">
                            <table className="w-full">
                                <thead className="bg-gray-700">
                                    <tr>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Name</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Type</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Files</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Size</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-700">
                                    {filteredItems.map((item, idx) => (
                                        <tr key={idx} className="hover:bg-gray-750 transition-colors">
                                            <td className="px-6 py-4 text-white font-medium">{item.name}</td>
                                            <td className="px-6 py-4">
                                                <span
                                                    className={`px-3 py-1 rounded-full text-xs font-medium ${item.type === 'Household'
                                                        ? 'bg-green-900 text-green-200'
                                                        : 'bg-purple-900 text-purple-200'
                                                        }`}
                                                >
                                                    {item.type}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-gray-300">{item.file_count} files</td>
                                            <td className="px-6 py-4 text-gray-300">{(item.size / 1024).toFixed(1)} KB</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {filteredItems.length === 0 && (
                        <div className="bg-gray-800 rounded-xl p-12 text-center text-gray-400">
                            <p>No tray items found</p>
                        </div>
                    )}
                </>
            )}

            {!trayScanResult && !isScanning && (
                <div className="bg-gray-800 rounded-xl p-12 text-center text-gray-400">
                    <Download size={64} className="mx-auto mb-4 opacity-50" />
                    <h3 className="text-xl font-bold text-white mb-2">No Scan Results</h3>
                    <p>Enter a path and click "Scan Folder" to analyze your tray files</p>
                </div>
            )}
        </div>
    );
}

export default TrayOrganizer;
