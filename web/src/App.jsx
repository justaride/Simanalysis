import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './views/Dashboard';
import ModManager from './views/ModManager';
import TrayOrganizer from './views/TrayOrganizer';
import SaveAnalyzer from './views/SaveAnalyzer';
import Conflicts from './views/Conflicts';
import Settings from './views/Settings';

function App() {
    return (
        <Layout>
            <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/mods" element={<ModManager />} />
                <Route path="/tray" element={<TrayOrganizer />} />
                <Route path="/save-analyzer" element={<SaveAnalyzer />} />
                <Route path="/conflicts" element={<Conflicts />} />
                <Route path="/settings" element={<Settings />} />
            </Routes>
        </Layout>
    );
}

export default App;
