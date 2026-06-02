import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';

const Dashboard = lazy(() => import('./views/Dashboard'));
const ModManager = lazy(() => import('./views/ModManager'));
const TrayOrganizer = lazy(() => import('./views/TrayOrganizer'));
const SaveAnalyzer = lazy(() => import('./views/SaveAnalyzer'));
const Conflicts = lazy(() => import('./views/Conflicts'));
const Doctor = lazy(() => import('./views/Doctor'));
const LiveMonitor = lazy(() => import('./views/LiveMonitor'));
const Treatment = lazy(() => import('./views/Treatment'));
const Settings = lazy(() => import('./views/Settings'));

function LoadingFallback() {
    return (
        <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
    );
}

function App() {
    return (
        <Layout>
            <Suspense fallback={<LoadingFallback />}>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/mods" element={<ModManager />} />
                    <Route path="/tray" element={<TrayOrganizer />} />
                    <Route path="/save-analyzer" element={<SaveAnalyzer />} />
                    <Route path="/conflicts" element={<Conflicts />} />
                    <Route path="/doctor" element={<Doctor />} />
                    <Route path="/live-monitor" element={<LiveMonitor />} />
                    <Route path="/treatment" element={<Treatment />} />
                    <Route path="/settings" element={<Settings />} />
                </Routes>
            </Suspense>
        </Layout>
    );
}

export default App;
