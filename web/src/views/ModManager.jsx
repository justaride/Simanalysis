import { useState, useEffect, forwardRef } from 'react';
import { Search, Filter, Download, Loader2, LayoutGrid, List as ListIcon, Package, FileCode, FolderOpen } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { toast } from 'sonner';
import { Virtuoso, VirtuosoGrid } from 'react-virtuoso';
import FilePicker from '../components/FilePicker';
import AnimatedProgress from '../components/AnimatedProgress';

function ModManager() {
    const { modScanResult, isScanning, scanProgress, startModScan, updateModScanProgress, completeModScan } = useAppContext();
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('all');
    const [scanPath, setScanPath] = useState('');
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('grid'); // 'list' or 'grid'
    const [showFilePicker, setShowFilePicker] = useState(false);

    // Load config on mount
    useEffect(() => {
        fetch('/api/config')
            .then(res => res.json())
            .then(data => {
                if (data.last_scan_path) {
                    setScanPath(data.last_scan_path);
                }
            })
            .catch(err => console.error("Failed to load config:", err));
    }, []);

    const handleScan = () => {
        if (!scanPath.trim()) {
            toast.error('Please enter a path');
            return;
        }

        setError(null);
        startModScan(scanPath);

        // Save config
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ last_scan_path: scanPath })
        }).catch(err => console.error("Failed to save config:", err));

        const toastId = toast.loading('Starting scan...');

        api.scanMods(scanPath, {
            onProgress: (progress) => {
                updateModScanProgress(progress);
                toast.loading(`Scanning: ${progress.file} `, { id: toastId });
            },
            onComplete: (result) => {
                completeModScan(result);
                toast.success(`Scan complete! Found ${result.summary.total_mods} mods.`, { id: toastId });
            },
            onError: (err) => {
                setError(err);
                completeModScan(null);
                toast.error(`Scan failed: ${err} `, { id: toastId });
            },
        });
    };

    // Use real mods from result or empty array
    const mods = modScanResult?.mods || [];

    // Helper to get conflicts for a mod
    const getModConflicts = (modName) => {
        if (!modScanResult?.conflicts) return [];
        return modScanResult.conflicts.filter(c => c.affected_mods.includes(modName));
    };

    const filteredMods = mods.filter((mod) => {
        const matchesSearch = mod.name.toLowerCase().includes(searchTerm.toLowerCase());

        let matchesFilter = false;
        if (filterType === 'all') {
            matchesFilter = true;
        } else if (filterType === 'missing_mesh') {
            const conflicts = getModConflicts(mod.name);
            matchesFilter = conflicts.some(c => c.type === 'DEPENDENCY_MISSING');
        } else {
            matchesFilter = mod.type.toLowerCase() === filterType;
        }

        return matchesSearch && matchesFilter;
    });

    const formatSize = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    // Virtualized Grid Components
    const GridList = forwardRef(({ children, ...props }, ref) => (
        <div
            ref={ref}
            {...props}
            className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 pb-4"
        >
            {children}
        </div>
    ));

    const GridItem = forwardRef(({ children, ...props }, ref) => (
        <div ref={ref} {...props} className="contents">
            {children}
        </div>
    ));

    return (
        <div className="p-8 h-screen flex flex-col">
            <div className="mb-8 shrink-0">
                <h1 className="text-3xl font-bold text-white">Mod Manager</h1>
                <p className="text-gray-400 mt-1">View and manage your installed mods</p>
            </div>

            {/* Scan Input */}
            <div className="bg-gray-800 p-6 rounded-xl mb-6 shrink-0">
                <div className="flex gap-4">
                    <div className="flex-1 flex gap-2">
                        <input
                            type="text"
                            placeholder="/path/to/Mods"
                            value={scanPath}
                            onChange={(e) => setScanPath(e.target.value)}
                            className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                        />
                        <button
                            onClick={() => setShowFilePicker(true)}
                            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg border border-gray-600 transition-colors"
                            title="Browse Folder"
                        >
                            <FolderOpen size={20} />
                        </button>
                    </div>
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
                                <Search size={20} />
                                <span>Scan Mods</span>
                            </>
                        )}
                    </button>
                </div>
                {error && <p className="text-red-500 mt-2">{error}</p>}

                {/* Progress Bar */}
                {isScanning && (
                    <div className="mt-6 flex justify-center">
                        <AnimatedProgress
                            progress={scanProgress.percentage}
                            status={scanProgress.file ? `Scanning: ${scanProgress.file.split('/').pop()}` : 'Processing...'}
                            size={180}
                        />
                    </div>
                )}
            </div>

            <FilePicker
                isOpen={showFilePicker}
                onClose={() => setShowFilePicker(false)}
                onSelect={(path) => setScanPath(path)}
                initialPath={scanPath || '~/Documents/Electronic Arts/The Sims 4/Mods'}
                selectDirectory={true}
                title="Select Mods Folder"
            />

            {modScanResult && (
                <>
                    {/* Toolbar */}
                    <div className="bg-gray-800 p-4 rounded-xl mb-6 flex flex-col md:flex-row gap-4 items-center shrink-0">
                        {/* Search */}
                        <div className="flex-1 relative w-full">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                            <input
                                type="text"
                                placeholder="Search mods..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full bg-gray-700 text-white px-10 py-2 rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
                            />
                        </div>

                        <div className="flex gap-4 w-full md:w-auto">
                            {/* Filter */}
                            <div className="flex items-center gap-2 bg-gray-700 rounded-lg px-3 border border-gray-600">
                                <Filter size={20} className="text-gray-400" />
                                <select
                                    value={filterType}
                                    onChange={(e) => setFilterType(e.target.value)}
                                    className="bg-transparent text-white py-2 focus:outline-none"
                                >
                                    <option value="all">All Types</option>
                                    <option value="script">Scripts</option>
                                    <option value="package">Packages</option>
                                    <option value="missing_mesh">Missing Meshes</option>
                                </select>
                            </div>

                            {/* View Toggle */}
                            <div className="flex bg-gray-700 rounded-lg p-1 border border-gray-600">
                                <button
                                    onClick={() => setViewMode('grid')}
                                    className={`p - 2 rounded - md transition - colors ${viewMode === 'grid' ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-white'} `}
                                    title="Grid View"
                                >
                                    <LayoutGrid size={20} />
                                </button>
                                <button
                                    onClick={() => setViewMode('list')}
                                    className={`p - 2 rounded - md transition - colors ${viewMode === 'list' ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-white'} `}
                                    title="List View"
                                >
                                    <ListIcon size={20} />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Results Summary */}
                    <div className="bg-blue-900/20 border border-blue-500 p-4 rounded-xl mb-6 shrink-0">
                        <p className="text-blue-200">
                            <strong>Scan Complete!</strong> Found {modScanResult.summary.total_mods} mods with{' '}
                            {modScanResult.summary.total_conflicts} conflicts.
                        </p>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-h-0">
                        {viewMode === 'list' ? (
                            <div className="bg-gray-800 rounded-xl overflow-hidden h-full flex flex-col">
                                <div className="bg-gray-700 px-6 py-4 grid grid-cols-12 gap-4 text-sm font-semibold text-gray-300 shrink-0">
                                    <div className="col-span-4">Name</div>
                                    <div className="col-span-2">Type</div>
                                    <div className="col-span-2">Size</div>
                                    <div className="col-span-2">Author</div>
                                    <div className="col-span-2">Status</div>
                                </div>
                                <Virtuoso
                                    data={filteredMods}
                                    itemContent={(index, mod) => {
                                        const conflicts = getModConflicts(mod.name);
                                        const hasMissingMesh = conflicts.some(c => c.type === 'DEPENDENCY_MISSING');

                                        return (
                                            <div className="px-6 py-4 grid grid-cols-12 gap-4 border-b border-gray-700 hover:bg-gray-750 transition-colors items-center">
                                                <div className="col-span-4 text-white font-medium flex items-center gap-3">
                                                    {mod.type === 'package' ? <Package size={16} className="text-blue-400 shrink-0" /> : <FileCode size={16} className="text-purple-400 shrink-0" />}
                                                    <span className="truncate" title={mod.name}>{mod.name}</span>
                                                </div>
                                                <div className="col-span-2">
                                                    <span className={`px - 3 py - 1 rounded - full text - xs font - medium ${mod.type === 'script' ? 'bg-purple-900 text-purple-200' : 'bg-blue-900 text-blue-200'} `}>
                                                        {mod.type}
                                                    </span>
                                                </div>
                                                <div className="col-span-2 text-gray-300">{formatSize(mod.size)}</div>
                                                <div className="col-span-2 text-gray-300 truncate">{mod.author}</div>
                                                <div className="col-span-2">
                                                    {hasMissingMesh ? (
                                                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-900 text-yellow-200">Missing Mesh</span>
                                                    ) : mod.conflicts > 0 ? (
                                                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-900 text-red-200">{mod.conflicts} Conflict{mod.conflicts > 1 ? 's' : ''}</span>
                                                    ) : (
                                                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-900 text-green-200">OK</span>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    }}
                                />
                            </div>
                        ) : (
                            <VirtuosoGrid
                                style={{ height: '100%' }}
                                totalCount={filteredMods.length}
                                components={{
                                    List: GridList,
                                    Item: GridItem,
                                }}
                                itemContent={(index) => {
                                    const mod = filteredMods[index];
                                    const conflicts = getModConflicts(mod.name);
                                    const hasMissingMesh = conflicts.some(c => c.type === 'DEPENDENCY_MISSING');

                                    return (
                                        <div className="bg-gray-800 rounded-xl overflow-hidden hover:ring-2 hover:ring-blue-500 transition-all group h-full">
                                            <div className="aspect-square bg-gray-900 relative overflow-hidden">
                                                {mod.type === 'package' ? (
                                                    <img
                                                        src={`/ api / mods / thumbnail ? path = ${encodeURIComponent(mod.path)} `}
                                                        alt={mod.name}
                                                        loading="lazy"
                                                        className="w-full h-full object-cover transition-transform group-hover:scale-105"
                                                        onError={(e) => {
                                                            e.target.onerror = null;
                                                            e.target.style.display = 'none';
                                                            e.target.nextSibling.style.display = 'flex';
                                                        }}
                                                    />
                                                ) : null}

                                                <div className="absolute inset-0 flex items-center justify-center bg-gray-800" style={{ display: mod.type === 'package' ? 'none' : 'flex' }}>
                                                    {mod.type === 'package' ? (
                                                        <Package size={48} className="text-gray-600" />
                                                    ) : (
                                                        <FileCode size={48} className="text-purple-500" />
                                                    )}
                                                </div>

                                                {hasMissingMesh ? (
                                                    <div className="absolute top-2 right-2 bg-yellow-600 text-white text-xs font-bold px-2 py-1 rounded-full shadow-lg">MESH?</div>
                                                ) : mod.conflicts > 0 && (
                                                    <div className="absolute top-2 right-2 bg-red-600 text-white text-xs font-bold px-2 py-1 rounded-full shadow-lg">!</div>
                                                )}
                                            </div>
                                            <div className="p-4">
                                                <h3 className="text-white font-medium truncate mb-1" title={mod.name}>{mod.name}</h3>
                                                <div className="flex justify-between items-center text-xs text-gray-400">
                                                    <span>{formatSize(mod.size)}</span>
                                                    <span className={mod.type === 'script' ? 'text-purple-400' : 'text-blue-400'}>{mod.type}</span>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                }}
                            />
                        )}
                    </div>

                    {filteredMods.length === 0 && (
                        <div className="p-12 text-center text-gray-400 bg-gray-800 rounded-xl mt-6 shrink-0">
                            <p>No mods found matching your criteria</p>
                        </div>
                    )}
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
