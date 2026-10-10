import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import pkg from './package.json'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const ssoEnabled = env.VITE_SSO_ENABLED === 'true'
  const ssoAuthOrigin = env.VITE_SSO_AUTH_ORIGIN || ''
  const ssoProviderName = env.VITE_SSO_PROVIDER_NAME || 'SSO'
  return {
  plugins: [tailwindcss(), react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __SSO_ENABLED__: JSON.stringify(ssoEnabled),
    __SSO_AUTH_ORIGIN__: JSON.stringify(ssoAuthOrigin),
    __SSO_PROVIDER_NAME__: JSON.stringify(ssoProviderName),
  },
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Forward cookies for session auth
            if (req.headers.cookie) {
              proxyReq.setHeader('Cookie', req.headers.cookie)
            }
          })
        },
      },
      // Legacy Gradio auth pages (still used by iframe)
      '/login': { target: 'http://localhost:8080', changeOrigin: true },
      '/auth':  { target: 'http://localhost:8080', changeOrigin: true },
      '/logout':{ target: 'http://localhost:8080', changeOrigin: true },
      // Gradio app (for iframe)
      '/main':  { target: 'http://localhost:8080', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Function form: Vite 8 (rolldown) no longer accepts the object form.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/node_modules\/(react|react-dom|react-router|react-router-dom)\//.test(id)) return 'vendor-react'
          if (/node_modules\/@assistant-ui\//.test(id)) return 'vendor-assistant'
          if (/node_modules\/@ag-ui\//.test(id)) return 'vendor-agui'
          return undefined
        },
      },
    },
  },
  }
})
