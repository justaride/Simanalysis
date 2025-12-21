import { useMemo } from 'react';
import { useAppContext } from '../context/AppContext';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { Activity, ShieldCheck, ShieldAlert, FileText, HardDrive, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';
import VisualConflictExplorer from '../components/VisualConflictExplorer';
import WelcomeHero from '../components/WelcomeHero';

function Dashboard() {
    const { modScanResult } = useAppContext();
    const conflicts = useMemo(() => modScanResult?.conflicts || [], [modScanResult?.conflicts]);
    const totalFiles = modScanResult?.total_files || 0;

    const stats = useMemo(() => {
        const severityCounts = {
            critical: conflicts.filter(c => c.severity === 'critical').length,
            high: conflicts.filter(c => c.severity === 'high').length,
            medium: conflicts.filter(c => c.severity === 'medium').length,
            low: conflicts.filter(c => c.severity === 'low').length,
        };

        const fileTypes = [
            { name: '.package', value: Math.floor(totalFiles * 0.8) },
            { name: '.ts4script', value: Math.floor(totalFiles * 0.2) },
        ];

        return { severityCounts, fileTypes };
    }, [conflicts, totalFiles]);

    const severityData = [
        { name: 'Critical', value: stats.severityCounts.critical, color: '#ef4444' },
        { name: 'High', value: stats.severityCounts.high, color: '#f97316' },
        { name: 'Medium', value: stats.severityCounts.medium, color: '#eab308' },
        { name: 'Low', value: stats.severityCounts.low, color: '#3b82f6' },
    ].filter(d => d.value > 0);

    const healthScore = Math.max(0, 100 - (stats.severityCounts.critical * 10) - (stats.severityCounts.high * 5) - (stats.severityCounts.medium * 2));

    const getHealthColor = (score) => {
        if (score >= 90) return 'text-green-400';
        if (score >= 70) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getHealthGradient = (score) => {
        if (score >= 90) return 'from-green-500/20 to-green-500/5';
        if (score >= 70) return 'from-yellow-500/20 to-yellow-500/5';
        return 'from-red-500/20 to-red-500/5';
    };

    if (!modScanResult) {
        return (
            <div className="h-full overflow-y-auto">
                <WelcomeHero />
            </div>
        );
    }

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: { staggerChildren: 0.1 },
        },
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
    };

    return (
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="h-full overflow-y-auto p-6 space-y-6"
        >
            <motion.header variants={itemVariants}>
                <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-xl">
                        <Activity className="text-blue-400" size={28} />
                    </div>
                    Dashboard
                </h1>
                <p className="text-gray-400 mt-2">Overview of your modding environment</p>
            </motion.header>

            {/* Top Stats Row */}
            <motion.div variants={itemVariants} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <motion.div
                    whileHover={{ scale: 1.02 }}
                    className={`glass-card p-6 flex flex-col items-center justify-center relative overflow-hidden bg-gradient-to-br ${getHealthGradient(healthScore)}`}
                >
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <ShieldCheck size={64} />
                    </div>
                    <span className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Game Health</span>
                    <div className={`text-5xl font-bold ${getHealthColor(healthScore)}`}>
                        {healthScore}%
                    </div>
                    <div className="flex items-center gap-1 text-xs text-gray-500 mt-2">
                        <TrendingUp size={12} />
                        Based on conflict severity
                    </div>
                </motion.div>

                <motion.div whileHover={{ scale: 1.02 }} className="glass-card p-6 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="p-2.5 bg-blue-500/20 rounded-xl text-blue-400">
                            <FileText size={22} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Total Mods</span>
                    </div>
                    <div className="text-4xl font-bold text-white">{totalFiles}</div>
                    <div className="text-xs text-gray-500 mt-1">Files scanned</div>
                </motion.div>

                <motion.div whileHover={{ scale: 1.02 }} className="glass-card p-6 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="p-2.5 bg-orange-500/20 rounded-xl text-orange-400">
                            <ShieldAlert size={22} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Conflicts</span>
                    </div>
                    <div className="text-4xl font-bold text-white">{conflicts.length}</div>
                    <div className="text-xs text-gray-500 mt-1">Issues detected</div>
                </motion.div>

                <motion.div whileHover={{ scale: 1.02 }} className="glass-card p-6 flex flex-col justify-center">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="p-2.5 bg-purple-500/20 rounded-xl text-purple-400">
                            <HardDrive size={22} />
                        </div>
                        <span className="text-gray-400 text-sm font-medium uppercase tracking-wider">Space Used</span>
                    </div>
                    <div className="text-4xl font-bold text-white">-- GB</div>
                    <div className="text-xs text-gray-500 mt-1">Estimated size</div>
                </motion.div>
            </motion.div>

            {/* Charts Row */}
            <motion.div variants={itemVariants} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-card p-6 h-[320px]">
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        Conflict Severity
                    </h3>
                    {severityData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="85%">
                            <PieChart>
                                <Pie
                                    data={severityData}
                                    cx="50%"
                                    cy="45%"
                                    innerRadius={55}
                                    outerRadius={85}
                                    paddingAngle={4}
                                    dataKey="value"
                                    stroke="none"
                                >
                                    {severityData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: 'rgba(31, 41, 55, 0.95)',
                                        borderColor: 'rgba(75, 85, 99, 0.5)',
                                        borderRadius: '12px',
                                        color: '#fff',
                                        backdropFilter: 'blur(8px)',
                                    }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Legend
                                    verticalAlign="bottom"
                                    height={36}
                                    formatter={(value) => <span className="text-gray-300 text-sm">{value}</span>}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-gray-500">
                            <ShieldCheck size={48} className="text-green-500/30 mb-3" />
                            <p className="text-green-400 font-medium">No conflicts detected</p>
                        </div>
                    )}
                </div>

                <div className="glass-card p-6 h-[320px]">
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-purple-500" />
                        File Distribution
                    </h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <BarChart data={stats.fileTypes} barCategoryGap="20%">
                            <XAxis
                                dataKey="name"
                                stroke="#6b7280"
                                tick={{ fill: '#9ca3af', fontSize: 12 }}
                                axisLine={{ stroke: '#374151' }}
                            />
                            <YAxis
                                stroke="#6b7280"
                                tick={{ fill: '#9ca3af', fontSize: 12 }}
                                axisLine={{ stroke: '#374151' }}
                            />
                            <Tooltip
                                cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }}
                                contentStyle={{
                                    backgroundColor: 'rgba(31, 41, 55, 0.95)',
                                    borderColor: 'rgba(75, 85, 99, 0.5)',
                                    borderRadius: '12px',
                                    color: '#fff',
                                    backdropFilter: 'blur(8px)',
                                }}
                            />
                            <Bar
                                dataKey="value"
                                fill="url(#barGradient)"
                                radius={[8, 8, 0, 0]}
                            />
                            <defs>
                                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#3b82f6" />
                                    <stop offset="100%" stopColor="#8b5cf6" />
                                </linearGradient>
                            </defs>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </motion.div>

            {/* Visual Conflict Explorer */}
            <motion.div variants={itemVariants}>
                <VisualConflictExplorer conflicts={conflicts} />
            </motion.div>
        </motion.div>
    );
}

export default Dashboard;
