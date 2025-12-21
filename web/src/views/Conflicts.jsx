import { useState, useMemo } from 'react';
import { useAppContext } from '../context/AppContext';
import { AlertTriangle, CheckCircle, Download, Copy } from 'lucide-react';
import { Virtuoso } from 'react-virtuoso';
import DuplicateModal from '../components/DuplicateModal';

function Conflicts() {
    const { modScanResult, refreshModScan } = useAppContext();
    const [selectedType, setSelectedType] = useState('all');
    const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
    const [selectedConflict, setSelectedConflict] = useState(null);

    const conflicts = useMemo(() => modScanResult?.conflicts || [], [modScanResult?.conflicts]);

    const stats = useMemo(() => {
        return {
            critical: conflicts.filter((c) => c.severity === 'critical').length,
            high: conflicts.filter((c) => c.severity === 'high').length,
            medium: conflicts.filter((c) => c.severity === 'medium').length,
            low: conflicts.filter((c) => c.severity === 'low').length,
        };
    }, [conflicts]);

    const filteredConflicts = useMemo(() => {
        if (selectedType === 'all') return conflicts;
        return conflicts.filter(c => c.severity === selectedType);
    }, [conflicts, selectedType]);

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'critical': return 'border-red-500 bg-red-900/20';
            case 'high': return 'border-orange-500 bg-orange-900/20';
            case 'medium': return 'border-yellow-500 bg-yellow-900/20';
            case 'low': return 'border-blue-500 bg-blue-900/20';
            default: return 'border-gray-500 bg-gray-900/20';
        }
    };

    const handleDownloadReport = () => {
        const report = JSON.stringify(modScanResult, null, 2);
        const blob = new Blob([report], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `simanalysis-report-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleManageDuplicates = (conflict) => {
        setSelectedConflict(conflict);
        setDuplicateModalOpen(true);
    };

    const handleFilesDeleted = () => {
        // Trigger a rescan or refresh the conflict data
        if (refreshModScan) {
            refreshModScan();
        }
    };

    const isDuplicateConflict = (conflict) => {
        return conflict.details?.file_hash !== undefined;
    };

    const ConflictCard = ({ conflict }) => (
        <div className={`border-l-4 ${getSeverityColor(conflict.severity)} bg-gray-800 p-4 rounded-r-xl mb-4`}>
            <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${conflict.severity === 'critical' ? 'bg-red-600 text-white' :
                            conflict.severity === 'high' ? 'bg-orange-600 text-white' :
                                conflict.severity === 'medium' ? 'bg-yellow-600 text-white' :
                                    'bg-blue-600 text-white'
                            }`}>
                            {conflict.severity}
                        </span>
                        <span className="text-gray-400 text-sm font-mono">{conflict.type}</span>
                        {isDuplicateConflict(conflict) && (
                            <span className="px-2 py-0.5 bg-purple-600 text-white rounded text-xs font-bold flex items-center gap-1">
                                <Copy size={12} />
                                DUPLICATE
                            </span>
                        )}
                    </div>
                    <p className="text-gray-200 text-sm">{conflict.description}</p>
                </div>
            </div>

            <div className="mt-3 bg-gray-900/50 p-3 rounded-lg">
                <p className="text-xs text-gray-500 mb-2 uppercase font-bold tracking-wider">Affected Mods</p>
                <div className="flex flex-wrap gap-2">
                    {conflict.affected_mods.map((mod, index) => (
                        <span key={index} className="px-2 py-1 bg-gray-800 border border-gray-700 text-gray-300 rounded text-xs truncate max-w-[300px]" title={mod}>
                            {mod}
                        </span>
                    ))}
                </div>
            </div>

            {isDuplicateConflict(conflict) && (
                <div className="mt-3">
                    <button
                        onClick={() => handleManageDuplicates(conflict)}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-sm font-medium flex items-center gap-2"
                    >
                        <Copy size={16} />
                        Manage Duplicates
                    </button>
                </div>
            )}
        </div>
    );

    return (
        <div className="h-full flex flex-col p-6">
            <div className="flex justify-between items-start mb-6 shrink-0">
                <div>
                    <h1 className="text-3xl font-bold text-white">Conflict Resolver</h1>
                    <p className="text-gray-400 mt-1">Found {conflicts.length} potential issues</p>
                </div>
                <button
                    onClick={handleDownloadReport}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                >
                    <Download size={18} />
                    Export Report
                </button>
            </div>

            {modScanResult ? (
                <>
                    {/* Summary Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 shrink-0">
                        <button
                            onClick={() => setSelectedType(selectedType === 'critical' ? 'all' : 'critical')}
                            className={`p-4 rounded-xl border transition-all text-left ${selectedType === 'critical' ? 'bg-red-900/30 border-red-500 ring-1 ring-red-500' : 'bg-gray-800 border-gray-700 hover:bg-gray-750'}`}
                        >
                            <p className="text-xs text-red-400 uppercase font-bold">Critical</p>
                            <p className="text-2xl font-bold text-white mt-1">{stats.critical}</p>
                        </button>
                        <button
                            onClick={() => setSelectedType(selectedType === 'high' ? 'all' : 'high')}
                            className={`p-4 rounded-xl border transition-all text-left ${selectedType === 'high' ? 'bg-orange-900/30 border-orange-500 ring-1 ring-orange-500' : 'bg-gray-800 border-gray-700 hover:bg-gray-750'}`}
                        >
                            <p className="text-xs text-orange-400 uppercase font-bold">High</p>
                            <p className="text-2xl font-bold text-white mt-1">{stats.high}</p>
                        </button>
                        <button
                            onClick={() => setSelectedType(selectedType === 'medium' ? 'all' : 'medium')}
                            className={`p-4 rounded-xl border transition-all text-left ${selectedType === 'medium' ? 'bg-yellow-900/30 border-yellow-500 ring-1 ring-yellow-500' : 'bg-gray-800 border-gray-700 hover:bg-gray-750'}`}
                        >
                            <p className="text-xs text-yellow-400 uppercase font-bold">Medium</p>
                            <p className="text-2xl font-bold text-white mt-1">{stats.medium}</p>
                        </button>
                        <button
                            onClick={() => setSelectedType(selectedType === 'low' ? 'all' : 'low')}
                            className={`p-4 rounded-xl border transition-all text-left ${selectedType === 'low' ? 'bg-blue-900/30 border-blue-500 ring-1 ring-blue-500' : 'bg-gray-800 border-gray-700 hover:bg-gray-750'}`}
                        >
                            <p className="text-xs text-blue-400 uppercase font-bold">Low</p>
                            <p className="text-2xl font-bold text-white mt-1">{stats.low}</p>
                        </button>
                    </div>

                    {/* Virtualized List */}
                    <div className="flex-1 min-h-0 bg-gray-900/30 rounded-xl border border-gray-800">
                        {filteredConflicts.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-gray-500">
                                <CheckCircle size={48} className="mb-4 text-green-500/50" />
                                <p className="text-lg font-medium">No conflicts found</p>
                                <p className="text-sm">Select a different filter or run a new scan</p>
                            </div>
                        ) : (
                            <Virtuoso
                                style={{ height: '100%' }}
                                data={filteredConflicts}
                                itemContent={(index, conflict) => (
                                    <div className="px-4 pt-4">
                                        <ConflictCard conflict={conflict} />
                                    </div>
                                )}
                            />
                        )}
                    </div>
                </>
            ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-gray-500 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
                    <AlertTriangle size={48} className="mb-4 opacity-50" />
                    <h3 className="text-xl font-bold text-white mb-2">No Scan Data</h3>
                    <p>Run a mod scan to detect conflicts</p>
                </div>
            )}

            <DuplicateModal
                isOpen={duplicateModalOpen}
                onClose={() => setDuplicateModalOpen(false)}
                conflict={selectedConflict}
                onFilesDeleted={handleFilesDeleted}
            />
        </div>
    );
}

export default Conflicts;
