import { useMemo } from 'react';
import { useAppContext } from '../context/AppContext';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { Activity, ShieldCheck, ShieldAlert, FileText, HardDrive } from 'lucide-react';
import VisualConflictExplorer from '../components/VisualConflictExplorer';

function Dashboard() {
    const { modScanResult } = useAppContext();
    const conflicts = modScanResult?.conflicts || [];
    const totalFiles = modScanResult?.total_files || 0;

    // Calculate stats
    const stats = useMemo(() => {
        const severityCounts = {
            critical: conflicts.filter(c => c.severity === 'critical').length,
            high: conflicts.filter(c => c.severity === 'high').length,
            medium: conflicts.filter(c => c.severity === 'medium').length,
            low: conflicts.filter(c => c.severity === 'low').length,
        };

        // Mock file types for now (backend needs to send this)
        const fileTypes = [
            { name: '.package', value: Math.floor(totalFiles * 0.8) },
            { name: '.ts4script', value: Math.floor(totalFiles * 0.2) },
        ];

        return { severityCounts, fileTypes };
    }, [conflicts, totalFiles]);

    // Data for Donut Chart
    const severityData = [
        { name: 'Critical', value: stats.severityCounts.critical, color: '#ef4444' },
        { name: 'High', value: stats.severityCounts.high, color: '#f97316' },
        { name: 'Medium', value: stats.severityCounts.medium, color: '#eab308' },
        { name: 'Low', value: stats.severityCounts.low, color: '#3b82f6' },
    ].filter(d => d.value > 0);

    // Calculate Health Score (0-100)
    const healthScore = Math.max(0, 100 - (stats.severityCounts.critical * 10) - (stats.severityCounts.high * 5) - (stats.severityCounts.medium * 2));

    const getHealthColor = (score) => {
        if (score >= 90) return 'text-green-500';
        if (score >= 70) return 'text-yellow-500';
        return 'text-red-500';
    };

    return (
        <div className="h-full overflow-y-auto p-6 space-y-6">
            <header>
                <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                    <Activity className="text-blue-500" />
                    Dashboard
                </h1>
                <p className="text-gray-400 mt-1">Overview of your modding environment</p>
            </header>

            {/* Top Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex flex-col items-center justify-center relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <ShieldCheck size={64} />
                    </div>
                    <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Game Health</span>
                    <div className={`text-5xl font-bold ${getHealthColor(healthScore)}`}>
                        {healthScore}%
                    </div>
                    <span className="text-xs text-gray-500 mt-2">Based on conflict severity</span>
                </div>

                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400">
                            <FileText size={24} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Total Mods</span>
                    </div>
                    <div className="text-3xl font-bold text-white ml-1">{totalFiles}</div>
                    <div className="text-xs text-gray-500 ml-1 mt-1">Files scanned</div>
                </div>

                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 bg-orange-500/20 rounded-lg text-orange-400">
                            <ShieldAlert size={24} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Conflicts</span>
                    </div>
                    <div className="text-3xl font-bold text-white ml-1">{conflicts.length}</div>
                    <div className="text-xs text-gray-500 ml-1 mt-1">Issues detected</div>
                </div>

                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 bg-purple-500/20 rounded-lg text-purple-400">
                            <HardDrive size={24} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Space Used</span>
                    </div>
                    <div className="text-3xl font-bold text-white ml-1">-- GB</div>
                    <div className="text-xs text-gray-500 ml-1 mt-1">Estimated size</div>
                </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Conflict Severity Chart */}
                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 h-[300px]">
                    <h3 className="text-lg font-bold text-white mb-4">Conflict Severity</h3>
                    {severityData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={severityData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {severityData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Legend verticalAlign="bottom" height={36} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-full flex items-center justify-center text-gray-500">
                            No conflicts detected
                        </div>
                    )}
                </div>

                {/* File Types Chart */}
                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 h-[300px]">
                    <h3 className="text-lg font-bold text-white mb-4">File Distribution</h3>
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={stats.fileTypes}>
                            <XAxis dataKey="name" stroke="#9ca3af" />
                            <YAxis stroke="#9ca3af" />
                            <Tooltip
                                cursor={{ fill: 'rgba(255, 255, 255, 0.1)' }}
                                contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
                            />
                            <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Visual Conflict Explorer */}
            <VisualConflictExplorer conflicts={conflicts} />
        </div>
    );
}

export default Dashboard;
