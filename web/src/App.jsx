import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';

const Dashboard = lazy(() => import('./views/Dashboard'));
const ModManager = lazy(() => import('./views/ModManager'));
const Inventory = lazy(() => import('./views/Inventory'));
const TrayOrganizer = lazy(() => import('./views/TrayOrganizer'));
const TrayProtector = lazy(() => import('./views/TrayProtector'));
const SaveAnalyzer = lazy(() => import('./views/SaveAnalyzer'));
const Conflicts = lazy(() => import('./views/Conflicts'));
const Cleanup = lazy(() => import('./views/Cleanup'));
const Doctor = lazy(() => import('./views/Doctor'));
const LiveMonitor = lazy(() => import('./views/LiveMonitor'));
const Treatment = lazy(() => import('./views/Treatment'));
const PatchDay = lazy(() => import('./views/PatchDay'));
const CacheDoctor = lazy(() => import('./views/CacheDoctor'));
const SaveProtector = lazy(() => import('./views/SaveProtector'));
const UpdateDesk = lazy(() => import('./views/UpdateDesk'));
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
                    <Route path="/inventory" element={<Inventory />} />
                    <Route path="/tray" element={<TrayOrganizer />} />
                    <Route path="/tray-protector" element={<TrayProtector />} />
                    <Route path="/save-analyzer" element={<SaveAnalyzer />} />
                    <Route path="/conflicts" element={<Conflicts />} />
                    <Route path="/cleanup" element={<Cleanup />} />
                    <Route path="/doctor" element={<Doctor />} />
                    <Route path="/live-monitor" element={<LiveMonitor />} />
                    <Route path="/treatment" element={<Treatment />} />
                    <Route path="/patch-day" element={<PatchDay />} />
                    <Route path="/cache-doctor" element={<CacheDoctor />} />
                    <Route path="/save-protector" element={<SaveProtector />} />
                    <Route path="/update-desk" element={<UpdateDesk />} />
                    <Route path="/settings" element={<Settings />} />
                </Routes>
            </Suspense>
        </Layout>
    );
}

export default App;
