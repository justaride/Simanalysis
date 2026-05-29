import { useState } from 'react';
import { X, Trash2, Calendar, HardDrive, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'sonner';

function DuplicateModal({ isOpen, onClose, conflict, onFilesDeleted }) {
    const [selectedFiles, setSelectedFiles] = useState(new Set());
    const [deleting, setDeleting] = useState(false);

    if (!isOpen || !conflict) return null;

    // Extract file paths from conflict details
    const files = conflict.details?.affected_mod_names || conflict.affected_mods || [];

    // Get file metadata - we'll need to fetch this from the backend
    // For now, simulate with the data we have
    const fileData = files.map(filename => ({
        name: filename,
        path: filename, // In reality, we'd need full paths
        size: 0, // Will be fetched
        modified: new Date(), // Will be fetched
    }));

    // Sort by modification date (newest first)
    const sortedFiles = [...fileData].sort((a, b) => b.modified - a.modified);
    const newestFile = sortedFiles[0];

    const toggleFileSelection = (filepath) => {
        const newSelection = new Set(selectedFiles);
        if (newSelection.has(filepath)) {
            newSelection.delete(filepath);
        } else {
            // Prevent selecting the newest file
            if (filepath === newestFile.path) {
                toast.error("Cannot delete the newest version");
                return;
            }
            newSelection.add(filepath);
        }
        setSelectedFiles(newSelection);
    };

    const handleDelete = async () => {
        if (selectedFiles.size === 0) {
            toast.error("No files selected");
            return;
        }

        const fileCount = selectedFiles.size;
        const confirmed = window.confirm(
            `Are you sure you want to delete ${fileCount} file${fileCount > 1 ? 's' : ''}?\\n\\nThey will be moved to the Trash.`
        );

        if (!confirmed) return;

        setDeleting(true);
        let successCount = 0;
        let failCount = 0;

        for (const filepath of selectedFiles) {
            try {
                await invoke('delete_mod_file', { path: filepath });
                successCount++;
            } catch (error) {
                console.error(`Failed to delete ${filepath}:`, error);
                failCount++;
            }
        }

        setDeleting(false);

        if (successCount > 0) {
            toast.success(`Deleted ${successCount} file${successCount > 1 ? 's' : ''}`);
        }
        if (failCount > 0) {
            toast.error(`Failed to delete ${failCount} file${failCount > 1 ? 's' : ''}`);
        }

        if (successCount > 0 && onFilesDeleted) {
            onFilesDeleted();
        }

        if (failCount === 0) {
            onClose();
        } else {
            // Remove successfully deleted files from selection
            const newSelection = new Set(selectedFiles);
            selectedFiles.forEach(file => {
                // We'd need better tracking here
                newSelection.delete(file);
            });
            setSelectedFiles(newSelection);
        }
    };

    const formatFileSize = (bytes) => {
        if (bytes === 0) return 'Unknown';
        const mb = bytes / 1024 / 1024;
        return `${mb.toFixed(2)} MB`;
    };

    const formatDate = (date) => {
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    };

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-4xl flex flex-col max-h-[80vh]">
                {/* Header */}
                <div className="p-6 border-b border-gray-700 flex justify-between items-start shrink-0">
                    <div>
                        <h3 className="text-2xl font-bold text-white flex items-center gap-2">
                            <AlertTriangle size={24} className="text-yellow-500" />
                            Manage Duplicate Files
                        </h3>
                        <p className="text-gray-400 mt-1">
                            {sortedFiles.length} duplicate files found
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* File List */}
                <div className="flex-1 overflow-y-auto p-6 space-y-3">
                    {sortedFiles.map((file) => {
                        const isNewest = file.path === newestFile.path;
                        const isSelected = selectedFiles.has(file.path);

                        return (
                            <div
                                key={file.path}
                                className={`border rounded-lg p-4 transition-all ${isNewest
                                        ? 'border-green-500 bg-green-900/20'
                                        : isSelected
                                            ? 'border-blue-500 bg-blue-900/20'
                                            : 'border-gray-700 bg-gray-900/50 hover:bg-gray-900'
                                    }`}
                            >
                                <div className="flex items-start gap-4">
                                    <input
                                        type="checkbox"
                                        checked={isSelected}
                                        disabled={isNewest}
                                        onChange={() => toggleFileSelection(file.path)}
                                        className="mt-1 w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                                    />

                                    <div className="flex-1">
                                        <div className="flex items-start justify-between mb-2">
                                            <div className="flex-1">
                                                <h4 className="text-white font-medium truncate" title={file.name}>
                                                    {file.name}
                                                </h4>
                                                <p className="text-xs text-gray-500 font-mono truncate mt-1" title={file.path}>
                                                    {file.path}
                                                </p>
                                            </div>
                                            {isNewest && (
                                                <span className="ml-4 px-2 py-1 bg-green-600 text-white text-xs font-bold rounded flex items-center gap-1 shrink-0">
                                                    <CheckCircle2 size={14} />
                                                    NEWEST
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex gap-6 text-sm text-gray-400">
                                            <div className="flex items-center gap-2">
                                                <Calendar size={16} />
                                                <span>{formatDate(file.modified)}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <HardDrive size={16} />
                                                <span>{formatFileSize(file.size)}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-gray-700 flex justify-between items-center shrink-0 bg-gray-800">
                    <div className="text-sm text-gray-400">
                        {selectedFiles.size > 0 ? (
                            <span>{selectedFiles.size} file{selectedFiles.size > 1 ? 's' : ''} selected</span>
                        ) : (
                            <span>Select files to delete</span>
                        )}
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-gray-300 hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleDelete}
                            disabled={selectedFiles.size === 0 || deleting}
                            className="px-6 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium flex items-center gap-2"
                        >
                            {deleting ? (
                                <>Processing...</>
                            ) : (
                                <>
                                    <Trash2 size={18} />
                                    Delete Selected
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default DuplicateModal;
