import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000';
const dashboardTarget = process.env.VITE_DASHBOARD_TARGET || 'http://localhost:8501';
const bridgeTarget = process.env.VITE_BRIDGE_TARGET || 'http://localhost:8522';

const registerBlockPlugin = {
  name: 'block-public-register',
  configureServer(server: any) {
    server.middlewares.use((req: any, res: any, next: any) => {
      if (req.method === 'POST' && req.url?.startsWith('/api/v1/auth/register')) {
        res.statusCode = 403;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ error: 'Registro público deshabilitado. Contacta al administrador.' }));
        return;
      }
      next();
    });
  },
};

export default defineConfig({
  plugins: [react(), registerBlockPlugin as any],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      // ─── Específicos primero (orden importa: first-match-wins) ─────
      // Bridge API via gateway. /api/v1/bridge/* → gateway :8000 → bridge :8522
      // El gateway valida el JWT y re-envía al bridge con el Authorization header.
      '/api/v1/bridge': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // Admin endpoints (Tenants & Billing) → bridge directo :8522
      // (el gateway no tiene ruta para /api/v1/admin)
      '/api/v1/admin': {
        target: 'http://localhost:8522',
        changeOrigin: true,
        rewrite: (path) => path,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // Auth endpoints → auth-service directo.
      '/api/v1/auth': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path,
      },
      // Live prices stream → gateway :8000 → bridge :8522
      '/api/v1/prices': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
      // Catch-all → gateway :8000 (signals, copy, risk, users, etc).
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

