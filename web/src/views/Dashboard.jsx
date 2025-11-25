import { useAppContext } from '../context/AppContext';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity, Package, HardDrive, Clock } from 'lucide-react';

function Dashboard() {
    const { modScanResult, trayScanResult } = useAppContext();

    // Calculate stats from scan results
    const hasModData = modScanResult?.summary;
    const hasTrayData = trayScanResult?.summary;

    const stats = {
        healthScore: hasModData
            ? Math.max(0, 100 - (modScanResult.summary.total_conflicts || 0) * 10)
            : 85,
        totalMods: modScanResult?.summary?.total_mods || 0,
        totalSize: modScanResult?.performance?.total_size_mb
            ? `${modScanResult.performance.total_size_mb.toFixed(1)} MB`
            : '0 MB',
        loadTime: modScanResult?.performance?.estimated_load_time_seconds
            ? `${modScanResult.performance.estimated_load_time_seconds.toFixed(1)}s`
            : '0s',
        conflicts: modScanResult?.summary?.total_conflicts || 0,
    };

    // Mock mod type data (in a real implementation, this would come from backend)
    const modTypeData = [
        { name: 'CAS', value: 120, color: '#3b82f6' },
        { name: 'Build/Buy', value: 80, color: '#10b981' },
        { name: 'Script', value: 47, color: '#f59e0b' },
    ];

    const storageData = [
        {
            category: 'Mods',
            size: modScanResult?.performance?.total_size_mb || 0
        },
        {
            category: 'Tray',
            size: trayScanResult?.summary?.total_size_mb || 0
        },
    ];

    return (
        <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Dashboard</h1>
                <p className="text-gray-400 mt-1">Overview of your Sims 4 game health</p>
            </div>

            {/* Health Score */}
            <div className="bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl p-8 mb-8">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-white text-lg mb-2">System Health</h2>
                        <div className="flex items-baseline gap-2">
                            <span className="text-6xl font-bold text-white">{stats.healthScore}</span>
                            <span className="text-2xl text-blue-200">/100</span>
                        </div>
                        <p className="text-blue-100 mt-2">
                            {stats.conflicts > 0 ? `${stats.conflicts} conflicts detected` : 'All systems normal'}
                        </p>
                    </div>
                    <Activity size={80} className="text-white opacity-20" />
                </div>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <StatCard icon={Package} title="Total Mods" value={stats.totalMods} color="blue" />
                <StatCard icon={HardDrive} title="Storage Used" value={stats.totalSize} color="green" />
                <StatCard icon={Clock} title="Load Time" value={stats.loadTime} color="yellow" />
                <StatCard
                    icon={Activity}
                    title="Conflicts"
                    value={stats.conflicts}
                    color={stats.conflicts > 0 ? 'red' : 'green'}
                />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Mod Type Distribution */}
                <div className="bg-gray-800 p-6 rounded-xl">
                    <h3 className="text-xl font-bold mb-4">Mod Type Distribution</h3>
                    {hasModData ? (
                        <ResponsiveContainer width="100%" height={250}>
                            <PieChart>
                                <Pie
                                    data={modTypeData}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {modTypeData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[250px] flex items-center justify-center text-gray-500">
                            <p>Run a mod scan to see distribution</p>
                        </div>
                    )}
                </div>

                {/* Storage Usage */}
                <div className="bg-gray-800 p-6 rounded-xl">
                    <h3 className="text-xl font-bold mb-4">Storage Usage (MB)</h3>
                    {hasModData || hasTrayData ? (
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={storageData}>
                                <XAxis dataKey="category" stroke="#9ca3af" />
                                <YAxis stroke="#9ca3af" />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
                                <Bar dataKey="size" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[250px] flex items-center justify-center text-gray-500">
                            <p>Run scans to see storage usage</p>
                        </div>
                    )}
                </div>
            </div>

            {!hasModData && !hasTrayData && (
                <div className="mt-8 bg-gray-800 rounded-xl p-12 text-center">
                    <Activity size={64} className="mx-auto mb-4 text-gray-600" />
                    <h3 className="text-xl font-bold text-white mb-2">No Scan Data</h3>
                    <p className="text-gray-400">
                        Visit "Mod Manager" or "Tray Organizer" to scan your files and populate the dashboard
                    </p>
                </div>
            )}
        </div>
    );
}

function StatCard({ icon: Icon, title, value, color }) {
    const colors = {
        blue: 'from-blue-600 to-blue-700',
        green: 'from-green-600 to-green-700',
        yellow: 'from-yellow-600 to-yellow-700',
        red: 'from-red-600 to-red-700',
    };

    return (
        <div className={`bg-gradient-to-br ${colors[color]} p-6 rounded-xl`}>
            <Icon className="text-white opacity-80 mb-2" size={24} />
            <p className="text-sm text-white opacity-90">{title}</p>
            <p className="text-3xl font-bold text-white mt-1">{value}</p>
        </div>
    );
}

export default Dashboard;
