import { useState, useEffect, forwardRef } from 'react';
import { Search, Filter, Download, Loader2, LayoutGrid, List as ListIcon, Package, FileCode, FolderOpen, Sparkles } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { toast } from 'sonner';
import { Virtuoso, VirtuosoGrid } from 'react-virtuoso';
import { motion, AnimatePresence } from 'framer-motion';
import FilePicker from '../components/FilePicker';
import AnimatedProgress from '../components/AnimatedProgress';
import ModThumbnail from '../components/ModThumbnail';

function ModManager() {
    const { modScanResult, isScanning, scanProgress, startModScan, updateModScanProgress, completeModScan } = useAppContext();
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('all');
    const [scanPath, setScanPath] = useState('');
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('grid');
    const [showFilePicker, setShowFilePicker] = useState(false);

    // Load config on mount
    useEffect(() => {
        invoke('get_config')
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
        invoke('set_config', { patch: { last_scan_path: scanPath } })
            .catch(err => console.error("Failed to save config:", err));

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
    const GridList = forwardRef(function GridList({ children, ...props }, ref) {
        return (
            <div
                ref={ref}
                {...props}
                className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 pb-4"
            >
                {children}
            </div>
        );
    });

    const GridItem = forwardRef(function GridItem({ children, ...props }, ref) {
        return (
            <div ref={ref} {...props} className="contents">
                {children}
            </div>
        );
    });

    return (
        <div className="p-8 h-screen flex flex-col">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-8 shrink-0"
            >
                <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-xl">
                        <Package className="text-blue-400" size={28} />
                    </div>
                    Mod Manager
                </h1>
                <p className="text-gray-400 mt-2">View and manage your installed mods</p>
            </motion.div>

            {/* Scan Input */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass-card p-6 mb-6 shrink-0"
            >
                <div className="flex gap-4">
                    <div className="flex-1 flex gap-2">
                        <input
                            type="text"
                            placeholder="/path/to/Mods"
                            value={scanPath}
                            onChange={(e) => setScanPath(e.target.value)}
                            className="flex-1 bg-gray-700/50 text-white px-4 py-3 rounded-xl border border-gray-600/50 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                        />
                        <button
                            onClick={() => setShowFilePicker(true)}
                            className="bg-gray-700/50 hover:bg-gray-600 text-white px-4 py-3 rounded-xl border border-gray-600/50 transition-all hover:border-gray-500"
                            title="Browse Folder"
                        >
                            <FolderOpen size={20} />
                        </button>
                    </div>
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleScan}
                        disabled={isScanning}
                        className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 disabled:opacity-50 text-white px-6 py-3 rounded-xl flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20"
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
                    </motion.button>
                </div>
                <AnimatePresence>
                    {error && (
                        <motion.p
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="text-red-400 mt-3"
                        >
                            {error}
                        </motion.p>
                    )}
                </AnimatePresence>

                {/* Progress Bar */}
                <AnimatePresence>
                    {isScanning && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            className="mt-6 flex justify-center"
                        >
                            <AnimatedProgress
                                progress={scanProgress.percentage}
                                status={scanProgress.file ? `Scanning: ${scanProgress.file.split('/').pop()}` : 'Processing...'}
                                size={180}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

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
                                        <motion.div
                                            initial={{ opacity: 0, scale: 0.95 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            transition={{ delay: index * 0.02, duration: 0.3 }}
                                            className="glass-card overflow-hidden card-hover group h-full"
                                        >
                                            <div className="aspect-square bg-gradient-to-br from-gray-800 to-gray-900 relative overflow-hidden">
                                                {mod.type === 'package' ? (
                                                    <ModThumbnail
                                                        path={mod.path}
                                                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900"
                                                    />
                                                ) : (
                                                    <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900">
                                                        <div className="p-4 bg-purple-500/20 rounded-2xl">
                                                            <FileCode size={40} className="text-purple-400" />
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                                                {hasMissingMesh ? (
                                                    <div className="absolute top-3 right-3 bg-yellow-500/90 backdrop-blur-sm text-white text-xs font-bold px-2.5 py-1 rounded-full shadow-lg flex items-center gap-1">
                                                        <Sparkles size={12} />
                                                        MESH?
                                                    </div>
                                                ) : mod.conflicts > 0 && (
                                                    <div className="absolute top-3 right-3 bg-red-500/90 backdrop-blur-sm text-white text-xs font-bold w-6 h-6 rounded-full shadow-lg flex items-center justify-center">!</div>
                                                )}
                                            </div>
                                            <div className="p-4">
                                                <h3 className="text-white font-medium truncate mb-2 group-hover:text-blue-400 transition-colors" title={mod.name}>{mod.name}</h3>
                                                <div className="flex justify-between items-center text-xs">
                                                    <span className="text-gray-400">{formatSize(mod.size)}</span>
                                                    <span className={`px-2 py-0.5 rounded-full ${mod.type === 'script' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'}`}>{mod.type}</span>
                                                </div>
                                            </div>
                                        </motion.div>
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
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="glass-card p-12 text-center flex-1 flex flex-col items-center justify-center"
                >
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center mb-6">
                        <Download size={40} className="text-blue-400" />
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-3">No Scan Results</h3>
                    <p className="text-gray-400 max-w-md">Enter the path to your Sims 4 Mods folder above and click &quot;Scan Mods&quot; to analyze your collection</p>
                </motion.div>
            )}
        </div>
    );
}

export default ModManager;
