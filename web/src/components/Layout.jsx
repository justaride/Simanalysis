import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

function Layout({ children }) {
    return (
        <div className="min-h-screen bg-gray-900 text-white flex">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                {children}
            </main>
        </div>
    );
}

export default Layout;
