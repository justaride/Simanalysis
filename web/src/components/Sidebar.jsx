import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Package, Home, FileSearch, AlertTriangle, Settings } from 'lucide-react';

function Sidebar() {
    const navItems = [
        { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
        { path: '/mods', icon: Package, label: 'Mod Manager' },
        { path: '/tray', icon: Home, label: 'Tray Organizer' },
        { path: '/save-analyzer', icon: FileSearch, label: 'Save Analyzer' },
        { path: '/conflicts', icon: AlertTriangle, label: 'Conflicts' },
        { path: '/settings', icon: Settings, label: 'Settings' },
    ];

    return (
        <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
            {/* Logo/Title */}
            <div className="p-6 border-b border-gray-700">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    🔬 <span>Simanalysis</span>
                </h1>
                <p className="text-xs text-gray-400 mt-1">Pro Edition</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4">
                <ul className="space-y-2">
                    {navItems.map((item) => (
                        <li key={item.path}>
                            <NavLink
                                to={item.path}
                                end={item.path === '/'}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive
                                        ? 'bg-blue-600 text-white font-medium'
                                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                                    }`
                                }
                            >
                                <item.icon size={20} />
                                <span>{item.label}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-gray-700">
                <p className="text-xs text-gray-500 text-center">v2.0.0</p>
            </div>
        </aside>
    );
}

export default Sidebar;
