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
      // ─── Específicos primero (orden importa: first-match-wins) ─────
      // Bridge API directo. /api/v1/bridge/* → :8522/api/v1/bridge/*
      // (la key debe matchear el path completo, NO un prefijo sin api/v1)
      '/api/v1/bridge': {
        target: bridgeTarget,
        changeOrigin: true,
        rewrite: (path) => path, // path ya viene con /api/v1/bridge, el bridge espera ese prefijo
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // Admin endpoints → auth-service directo (gateway no los enruta).
      '/api/v1/admin': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // Auth endpoints → auth-service directo. Sin este proxy, los auth/*
      // caen en el catch-all '/api' y el gateway devuelve 503 (su
      // services.json apunta a hostname docker 'auth-service' que no
      // resuelve en Windows nativos).
      '/api/v1/auth': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path,
      },
      // Users endpoints → auth-service directo (no hay user-service
      // corriendo, pero el gateway tampoco puede forwardear).
      '/api/v1/users': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      // Catch-all → gateway :8000 (signals, copy, risk, prices, etc
      // — que NO corren en dev, así que 502 es la respuesta esperada).
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
    },
  },
  clearScreen: false,
});

