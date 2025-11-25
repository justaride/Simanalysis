import { useAppContext } from '../context/AppContext';
import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

function Conflicts() {
    const { modScanResult } = useAppContext();

    const conflicts = modScanResult?.conflicts || [];

    const criticalCount = conflicts.filter((c) => c.severity === 'critical').length;
    const highCount = conflicts.filter((c) => c.severity === 'high').length;

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'critical':
                return 'border-red-500 bg-red-900/20';
            case 'high':
                return 'border-orange-500 bg-orange-900/20';
            case 'medium':
                return 'border-yellow-500 bg-yellow-900/20';
            case 'low':
                return 'border-blue-500 bg-blue-900/20';
            default:
                return 'border-gray-500 bg-gray-900/20';
        }
    };

    const gameHealth = conflicts.length === 0 ? 'Excellent' : criticalCount > 0 ? 'Poor' : highCount > 3 ? 'Fair' : 'Good';

    return (
        <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Conflict Resolver</h1>
                <p className="text-gray-400 mt-1">Identify and resolve mod conflicts</p>
            </div>

            {modScanResult ? (
                <>
                    {/* Summary */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div className="bg-red-900/20 border border-red-500 p-6 rounded-xl">
                            <XCircle className="text-red-400 mb-2" size={32} />
                            <p className="text-sm text-red-200">Critical Issues</p>
                            <p className="text-3xl font-bold text-red-400 mt-1">{criticalCount}</p>
                        </div>
                        <div className="bg-orange-900/20 border border-orange-500 p-6 rounded-xl">
                            <AlertTriangle className="text-orange-400 mb-2" size={32} />
                            <p className="text-sm text-orange-200">High Priority</p>
                            <p className="text-3xl font-bold text-orange-400 mt-1">{highCount}</p>
                        </div>
                        <div
                            className={`p-6 rounded-xl ${gameHealth === 'Excellent'
                                    ? 'bg-green-900/20 border border-green-500'
                                    : gameHealth === 'Good'
                                        ? 'bg-blue-900/20 border border-blue-500'
                                        : gameHealth === 'Fair'
                                            ? 'bg-yellow-900/20 border border-yellow-500'
                                            : 'bg-red-900/20 border border-red-500'
                                }`}
                        >
                            <CheckCircle
                                className={`mb-2 ${gameHealth === 'Excellent'
                                        ? 'text-green-400'
                                        : gameHealth === 'Good'
                                            ? 'text-blue-400'
                                            : gameHealth === 'Fair'
                                                ? 'text-yellow-400'
                                                : 'text-red-400'
                                    }`}
                                size={32}
                            />
                            <p
                                className={`text-sm ${gameHealth === 'Excellent'
                                        ? 'text-green-200'
                                        : gameHealth === 'Good'
                                            ? 'text-blue-200'
                                            : gameHealth === 'Fair'
                                                ? 'text-yellow-200'
                                                : 'text-red-200'
                                    }`}
                            >
                                Game Health
                            </p>
                            <p
                                className={`text-3xl font-bold mt-1 ${gameHealth === 'Excellent'
                                        ? 'text-green-400'
                                        : gameHealth === 'Good'
                                            ? 'text-blue-400'
                                            : gameHealth === 'Fair'
                                                ? 'text-yellow-400'
                                                : 'text-red-400'
                                    }`}
                            >
                                {gameHealth}
                            </p>
                        </div>
                    </div>

                    {/* Conflicts List */}
                    <div className="space-y-4">
                        {conflicts.length === 0 ? (
                            <div className="bg-gray-800 rounded-xl p-12 text-center">
                                <CheckCircle className="text-green-500 mx-auto mb-4" size={64} />
                                <h3 className="text-2xl font-bold text-white mb-2">No Conflicts Detected!</h3>
                                <p className="text-gray-400">Your mod setup looks clean</p>
                            </div>
                        ) : (
                            conflicts.map((conflict) => (
                                <div
                                    key={conflict.id}
                                    className={`border-l-4 ${getSeverityColor(
                                        conflict.severity
                                    )} bg-gray-800 p-6 rounded-xl`}
                                >
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <div className="flex items-center gap-3 mb-2">
                                                <h3 className="text-xl font-bold text-white">{conflict.type}</h3>
                                                <span
                                                    className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${conflict.severity === 'critical'
                                                            ? 'bg-red-600 text-white'
                                                            : conflict.severity === 'high'
                                                                ? 'bg-orange-600 text-white'
                                                                : conflict.severity === 'medium'
                                                                    ? 'bg-yellow-600 text-white'
                                                                    : 'bg-blue-600 text-white'
                                                        }`}
                                                >
                                                    {conflict.severity}
                                                </span>
                                            </div>
                                            <p className="text-gray-300">{conflict.description}</p>
                                        </div>
                                    </div>

                                    {/* Affected Mods */}
                                    <div className="mb-4">
                                        <p className="text-sm text-gray-400 mb-2">Affected Mods:</p>
                                        <div className="flex flex-wrap gap-2">
                                            {conflict.affected_mods.map((mod, index) => (
                                                <span
                                                    key={index}
                                                    className="px-3 py-1 bg-gray-700 text-white rounded-lg text-sm"
                                                >
                                                    {mod}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Resolution */}
                                    {conflict.resolution && (
                                        <div className="mb-4 p-4 bg-blue-900/20 border border-blue-500 rounded-lg">
                                            <p className="text-sm text-blue-200 font-medium mb-1">💡 Recommended Action:</p>
                                            <p className="text-blue-100">{conflict.resolution}</p>
                                        </div>
                                    )}

                                    {/* Actions */}
                                    <div className="flex gap-2">
                                        <button className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors">
                                            Resolve
                                        </button>
                                        <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                                            Ignore
                                        </button>
                                        <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                                            More Info
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </>
            ) : (
                <div className="bg-gray-800 rounded-xl p-12 text-center text-gray-400">
                    <AlertTriangle size={64} className="mx-auto mb-4 opacity-50" />
                    <h3 className="text-xl font-bold text-white mb-2">No Scan Data</h3>
                    <p>Run a mod scan to detect conflicts</p>
                </div>
            )}
        </div>
    );
}

export default Conflicts;
