import React, { useState, useEffect } from 'react';
import { X, Folder, File, ChevronUp, Loader2, HardDrive } from 'lucide-react';

function FilePicker({ isOpen, onClose, onSelect, initialPath, selectDirectory = true, title = "Select Path" }) {
    const [currentPath, setCurrentPath] = useState(initialPath || '');
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [selectedItem, setSelectedItem] = useState(null);

    useEffect(() => {
        if (isOpen) {
            loadPath(initialPath || '');
        }
    }, [isOpen, initialPath]);

    const loadPath = async (path) => {
        setLoading(true);
        setError(null);
        setSelectedItem(null);
        try {
            const url = path
                ? `/api/system/browse?path=${encodeURIComponent(path)}`
                : '/api/system/browse';

            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to load directory');

            const data = await res.json();
            setItems(data.items);
            setCurrentPath(data.current_path);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleItemClick = (item) => {
        if (item.is_parent) {
            loadPath(item.path);
            return;
        }

        setSelectedItem(item);

        // Double click behavior for directories
        if (item.type === 'directory') {
            // We'll handle double click separately if needed, 
            // but for now single click selects, double click enters
        }
    };

    const handleItemDoubleClick = (item) => {
        if (item.type === 'directory' || item.is_parent) {
            loadPath(item.path);
        }
    };

    const handleSelect = () => {
        if (selectDirectory) {
            // If selecting directory, we can select the current path OR a selected subdirectory
            if (selectedItem && selectedItem.type === 'directory') {
                onSelect(selectedItem.path);
            } else {
                // If nothing selected (or file selected but we want dir), select current folder
                onSelect(currentPath);
            }
        } else {
            // Selecting file
            if (selectedItem && selectedItem.type === 'file') {
                onSelect(selectedItem.path);
            }
        }
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[80vh]">
                {/* Header */}
                <div className="p-4 border-b border-gray-700 flex justify-between items-center shrink-0">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <HardDrive size={20} className="text-blue-400" />
                        {title}
                    </h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                        <X size={24} />
                    </button>
                </div>

                {/* Path Bar */}
                <div className="px-4 py-2 bg-gray-900/50 border-b border-gray-700 text-sm text-gray-300 truncate shrink-0">
                    {currentPath || 'Home'}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-2 min-h-0">
                    {loading ? (
                        <div className="flex items-center justify-center h-40">
                            <Loader2 className="animate-spin text-blue-500" size={32} />
                        </div>
                    ) : error ? (
                        <div className="text-center text-red-400 p-8">
                            <p>{error}</p>
                            <button
                                onClick={() => loadPath('')}
                                className="mt-4 px-4 py-2 bg-gray-700 rounded hover:bg-gray-600 text-white text-sm"
                            >
                                Go Home
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {items.map((item, idx) => (
                                <div
                                    key={idx}
                                    onClick={() => handleItemClick(item)}
                                    onDoubleClick={() => handleItemDoubleClick(item)}
                                    className={`
                                        flex items-center gap-3 px-3 py-2 rounded cursor-pointer transition-colors select-none
                                        ${selectedItem?.path === item.path
                                            ? 'bg-blue-600/30 text-white ring-1 ring-blue-500'
                                            : 'text-gray-300 hover:bg-gray-700'}
                                    `}
                                >
                                    {item.is_parent ? (
                                        <ChevronUp size={20} className="text-gray-500" />
                                    ) : item.type === 'directory' ? (
                                        <Folder size={20} className="text-yellow-500 fill-yellow-500/20" />
                                    ) : (
                                        <File size={20} className="text-gray-500" />
                                    )}
                                    <span className="truncate flex-1">{item.name}</span>
                                    {!item.is_parent && (
                                        <span className="text-xs text-gray-500 w-20 text-right">
                                            {item.type === 'file' && item.size ? (item.size / 1024).toFixed(1) + ' KB' : ''}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-700 flex justify-end gap-3 shrink-0 bg-gray-800 rounded-b-xl">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-300 hover:text-white transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSelect}
                        disabled={loading || (!selectedItem && !selectDirectory)}
                        className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
                    >
                        {selectDirectory
                            ? (selectedItem?.type === 'directory' ? 'Select Folder' : 'Select Current Folder')
                            : 'Select File'
                        }
                    </button>
                </div>
            </div>
        </div>
    );
}

export default FilePicker;
