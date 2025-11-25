import React from 'react';

function TrayResults({ result }) {
    if (!result) return null;

    const { summary, items } = result;

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card title="Total Items" value={summary.total_items} color="blue" />
                <Card title="Households" value={summary.households} color="green" />
                <Card title="Lots & Rooms" value={summary.lots_rooms} color="purple" />
            </div>

            {/* Items List */}
            <div className="bg-gray-800 p-6 rounded-lg shadow">
                <h2 className="text-xl font-bold mb-4">📂 Tray Items</h2>
                {items.length === 0 ? (
                    <p className="text-gray-400">No tray items found.</p>
                ) : (
                    <div className="space-y-4">
                        {items.map((item, index) => (
                            <div key={index} className="bg-gray-700 p-4 rounded border-l-4 border-blue-500">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <h3 className="font-bold text-white text-lg">{item.name}</h3>
                                        <span className="bg-blue-900 text-blue-200 text-xs px-2 py-1 rounded mt-1 inline-block">
                                            {item.type}
                                        </span>
                                    </div>
                                    <div className="text-right text-sm text-gray-400">
                                        <div>{item.file_count} files</div>
                                        <div>{(item.size / 1024).toFixed(1)} KB</div>
                                    </div>
                                </div>
                                <div className="mt-2 text-xs text-gray-500">
                                    Files: {item.files.slice(0, 3).join(', ')}
                                    {item.files.length > 3 && ` +${item.files.length - 3} more`}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function Card({ title, value, color }) {
    const colors = {
        blue: 'text-blue-400',
        green: 'text-green-400',
        purple: 'text-purple-400',
        yellow: 'text-yellow-400',
    };

    return (
        <div className="bg-gray-800 p-6 rounded-lg shadow">
            <h3 className="text-gray-400 text-sm font-medium uppercase">{title}</h3>
            <p className={`text-3xl font-bold mt-2 ${colors[color] || 'text-white'}`}>{value}</p>
        </div>
    );
}

export default TrayResults;
