import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import pkg from './package.json'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const ssoAuthOrigin = env.VITE_SSO_AUTH_ORIGIN || 'https://auth.myners.net'
  const ssoProviderName = env.VITE_SSO_PROVIDER_NAME || 'SSO'
  return {
  plugins: [tailwindcss(), react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
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
            // Forward the SSO cookie
            if (req.headers.cookie) {
              proxyReq.setHeader('Cookie', req.headers.cookie)
            }
          })
        },
      },
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
