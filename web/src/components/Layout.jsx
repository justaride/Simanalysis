import { useEffect } from 'react';
import Sidebar from './Sidebar';
import { Toaster, toast } from 'sonner';
import { Download } from 'lucide-react';

function Layout({ children }) {
    useEffect(() => {
        // Check for updates
        fetch('/api/updates')
            .then(res => res.json())
            .then(update => {
                if (update) {
                    toast('New Update Available!', {
                        description: `Version ${update.version} is now available.`,
                        action: {
                            label: 'Download',
                            onClick: () => window.open(update.download_url, '_blank')
                        },
                        duration: Infinity, // Stay until dismissed
                        icon: <Download size={18} />
                    });
                }
            })
            .catch(err => console.error("Failed to check for updates:", err));
    }, []);

    return (
        <div className="min-h-screen bg-gray-900 text-white flex">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                {children}
            </main>
            <Toaster position="top-right" theme="dark" />
        </div>
    );
}

export default Layout;
