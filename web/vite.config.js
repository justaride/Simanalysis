import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const chunkPackages = {
    vendor: ['react', 'react-dom', 'react-router-dom'],
    charts: ['recharts'],
    animations: ['framer-motion'],
    ui: ['@headlessui/react', 'clsx', 'tailwind-merge'],
}

function manualChunks(id) {
    const normalized = id.replaceAll('\\', '/')
    const marker = '/node_modules/'
    const markerIndex = normalized.lastIndexOf(marker)
    if (markerIndex === -1) return undefined

    const packagePath = normalized.slice(markerIndex + marker.length)
    for (const [chunkName, packageNames] of Object.entries(chunkPackages)) {
        if (packageNames.some((packageName) => (
            packagePath === packageName || packagePath.startsWith(`${packageName}/`)
        ))) {
            return chunkName
        }
    }
    return undefined
}

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    base: './',
    clearScreen: false,
    server: { port: 5173, strictPort: true },
    build: {
        rollupOptions: {
            output: {
                manualChunks,
            }
        }
    },
})
