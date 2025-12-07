import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, FileWarning, Copy } from 'lucide-react';

function VisualConflictExplorer({ conflicts }) {
    // Process conflicts into a simpler node-link structure for visualization
    const data = useMemo(() => {
        if (!conflicts || conflicts.length === 0) return { nodes: [], links: [] };

        const nodes = [];
        const links = [];
        const nodeMap = new Set();

        // Limit to top 20 conflicts to prevent visual clutter
        const topConflicts = conflicts.slice(0, 20);

        topConflicts.forEach((conflict, index) => {
            // Create a central node for the conflict itself
            const conflictId = `conflict-${index}`;
            nodes.push({
                id: conflictId,
                type: 'conflict',
                severity: conflict.severity,
                label: conflict.type,
                details: conflict.description
            });

            // Create nodes for affected mods
            conflict.affected_mods.forEach(mod => {
                if (!nodeMap.has(mod)) {
                    nodes.push({
                        id: mod,
                        type: 'mod',
                        label: mod.split('/').pop(), // Show only filename
                        fullPath: mod
                    });
                    nodeMap.add(mod);
                }

                // Link mod to conflict
                links.push({
                    source: conflictId,
                    target: mod
                });
            });
        });

        return { nodes, links };
    }, [conflicts]);

    if (!conflicts || conflicts.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-gray-500 bg-gray-800/30 rounded-xl border border-gray-700 border-dashed">
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4">
                    <AlertTriangle size={32} className="text-gray-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-300">No Conflicts to Visualize</h3>
                <p className="text-sm mt-2">Run a scan to see conflict relationships here.</p>
            </div>
        );
    }

    return (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <FileWarning className="text-purple-400" />
                Conflict Visualizer
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.nodes.filter(n => n.type === 'conflict').map((node) => (
                    <motion.div
                        key={node.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`p-4 rounded-lg border ${node.severity === 'critical' ? 'border-red-500/50 bg-red-900/10' :
                                node.severity === 'high' ? 'border-orange-500/50 bg-orange-900/10' :
                                    'border-blue-500/50 bg-blue-900/10'
                            }`}
                    >
                        <div className="flex items-start gap-3">
                            <div className={`p-2 rounded-lg ${node.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                    node.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                        'bg-blue-500/20 text-blue-400'
                                }`}>
                                {node.label === 'Hash Collision' ? <Copy size={18} /> : <AlertTriangle size={18} />}
                            </div>
                            <div>
                                <h4 className="font-bold text-gray-200 text-sm">{node.label}</h4>
                                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{node.details}</p>

                                <div className="mt-3 flex flex-wrap gap-2">
                                    {data.links
                                        .filter(l => l.source === node.id)
                                        .map(l => (
                                            <span key={l.target} className="px-2 py-1 bg-gray-900/50 rounded text-[10px] text-gray-400 border border-gray-700 truncate max-w-[150px]">
                                                {l.target.split('/').pop()}
                                            </span>
                                        ))
                                    }
                                </div>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>

            <div className="mt-4 text-center">
                <p className="text-xs text-gray-500">
                    Showing top {Math.min(conflicts.length, 20)} conflicts. View full list in the Conflicts tab.
                </p>
            </div>
        </div>
    );
}

export default VisualConflictExplorer;
