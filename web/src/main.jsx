import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AppProvider } from './context/AppContext'
import { LiveMonitorProvider } from './context/LiveMonitorContext'
import ErrorBoundary from './components/ErrorBoundary'
import './index.css'

createRoot(document.getElementById('root')).render(
    <StrictMode>
        <ErrorBoundary>
            <BrowserRouter>
                <AppProvider>
                    <LiveMonitorProvider>
                        <App />
                    </LiveMonitorProvider>
                </AppProvider>
            </BrowserRouter>
        </ErrorBoundary>
    </StrictMode>,
)
