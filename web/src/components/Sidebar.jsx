import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Package, Home, FileSearch, AlertTriangle, Settings, ChevronLeft, ChevronRight, Microscope, Stethoscope } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function isCompactViewport() {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(max-width: 767px)').matches;
}

function Sidebar() {
    const [collapsed, setCollapsed] = useState(() => {
        const saved = localStorage.getItem('sidebar-collapsed');
        return isCompactViewport() || (saved ? JSON.parse(saved) : false);
    });

    useEffect(() => {
        if (!isCompactViewport()) {
            localStorage.setItem('sidebar-collapsed', JSON.stringify(collapsed));
        }
    }, [collapsed]);

    useEffect(() => {
        const query = window.matchMedia('(max-width: 767px)');
        const syncCompactState = (event) => {
            if (event.matches) {
                setCollapsed(true);
                return;
            }
            const saved = localStorage.getItem('sidebar-collapsed');
            setCollapsed(saved ? JSON.parse(saved) : false);
        };

        query.addEventListener('change', syncCompactState);
        return () => query.removeEventListener('change', syncCompactState);
    }, []);

    const navItems = [
        { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
        { path: '/mods', icon: Package, label: 'Mod Manager' },
        { path: '/tray', icon: Home, label: 'Tray Organizer' },
        { path: '/save-analyzer', icon: FileSearch, label: 'Save Analyzer' },
        { path: '/conflicts', icon: AlertTriangle, label: 'Conflicts' },
        { path: '/doctor', icon: Microscope, label: 'Doctor' },
        { path: '/treatment', icon: Stethoscope, label: 'Treatment' },
        { path: '/settings', icon: Settings, label: 'Settings' },
    ];

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? 80 : 256 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="bg-gradient-to-b from-gray-800 to-gray-900 border-r border-gray-700/50 flex flex-col relative group"
        >
            {/* Collapse Toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="absolute -right-3 top-20 z-10 w-6 h-6 bg-gray-700 border border-gray-600 rounded-full flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-600 transition-all opacity-0 group-hover:opacity-100 shadow-lg"
            >
                {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            </button>

            {/* Logo/Title */}
            <div className="p-4 border-b border-gray-700/50">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg shadow-blue-500/20">
                        <Microscope size={22} className="text-white" />
                    </div>
                    <AnimatePresence>
                        {!collapsed && (
                            <motion.div
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.15 }}
                            >
                                <h1 className="text-lg font-bold text-white whitespace-nowrap">Simanalysis</h1>
                                <p className="text-xs text-gray-400">Pro Edition</p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 overflow-y-auto">
                <ul className="space-y-1">
                    {navItems.map((item) => (
                        <li key={item.path}>
                            <NavLink
                                to={item.path}
                                end={item.path === '/'}
                                title={collapsed ? item.label : undefined}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 relative overflow-hidden ${isActive
                                        ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white font-medium shadow-lg shadow-blue-500/20'
                                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'
                                    } ${collapsed ? 'justify-center' : ''}`
                                }
                            >
                                {({ isActive }) => (
                                    <>
                                        <item.icon size={20} className={`shrink-0 ${isActive ? 'text-white' : ''}`} />
                                        <AnimatePresence>
                                            {!collapsed && (
                                                <motion.span
                                                    initial={{ opacity: 0, x: -10 }}
                                                    animate={{ opacity: 1, x: 0 }}
                                                    exit={{ opacity: 0, x: -10 }}
                                                    transition={{ duration: 0.15 }}
                                                    className="whitespace-nowrap"
                                                >
                                                    {item.label}
                                                </motion.span>
                                            )}
                                        </AnimatePresence>
                                        {isActive && (
                                            <motion.div
                                                layoutId="activeIndicator"
                                                className="absolute inset-0 bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl -z-10"
                                                transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                                            />
                                        )}
                                    </>
                                )}
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-gray-700/50">
                <AnimatePresence mode="wait">
                    {collapsed ? (
                        <motion.p
                            key="collapsed"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="text-xs text-gray-500 text-center"
                        >
                            2.0
                        </motion.p>
                    ) : (
                        <motion.div
                            key="expanded"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex items-center justify-between text-xs text-gray-500"
                        >
                            <span>v2.0.0</span>
                            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">Stable</span>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.aside>
    );
}

export default Sidebar;
