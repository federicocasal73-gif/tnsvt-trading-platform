import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000';
const dashboardTarget = process.env.VITE_DASHBOARD_TARGET || 'http://localhost:8501';
const bridgeTarget = process.env.VITE_BRIDGE_TARGET || 'http://localhost:8522';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // MT5 bot Streamlit dashboard embebido en :5180/mt5-bot
      '/mt5-bot-iframe': {
        target: dashboardTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mt5-bot-iframe/, ''),
        ws: true,
      },
      // Bridge API para llamadas directas desde el frontend (si se necesitan)
      '/bridge-direct': {
        target: bridgeTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/bridge-direct/, ''),
      },
    },
  },
  clearScreen: false,
});

