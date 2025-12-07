import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("Uncaught error:", error, errorInfo);
        this.setState({ errorInfo });
    }

    handleReload = () => {
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
                    <div className="bg-gray-800 p-8 rounded-2xl max-w-md w-full text-center border border-red-900/50 shadow-2xl">
                        <div className="bg-red-900/20 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
                            <AlertTriangle size={40} className="text-red-500" />
                        </div>

                        <h1 className="text-2xl font-bold text-white mb-2">Something went wrong</h1>
                        <p className="text-gray-400 mb-6">
                            The application encountered an unexpected error.
                        </p>

                        <div className="bg-gray-900 rounded-lg p-4 mb-6 text-left overflow-auto max-h-40">
                            <code className="text-xs text-red-400 font-mono block">
                                {this.state.error && this.state.error.toString()}
                            </code>
                        </div>

                        <button
                            onClick={this.handleReload}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg flex items-center justify-center gap-2 w-full transition-colors font-medium"
                        >
                            <RefreshCw size={20} />
                            Reload Application
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
