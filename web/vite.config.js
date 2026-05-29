import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    base: './',
    clearScreen: false,
    server: { port: 5173, strictPort: true },
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    vendor: ['react', 'react-dom', 'react-router-dom'],
                    charts: ['recharts'],
                    animations: ['framer-motion'],
                    ui: ['@headlessui/react', 'clsx', 'tailwind-merge'],
                }
            }
        }
    },
})
