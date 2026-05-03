import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/** Dev: proxy `/config`, `/ingest`, … to FastAPI. Production static deploy: DEPLOY_STATIC=1 writes to repo `static/`. */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_API || 'http://127.0.0.1:8000'
  const deployStatic = env.DEPLOY_STATIC === '1'

  return {
    plugins: [react()],
    build: deployStatic ? { outDir: '../static', emptyOutDir: true } : {},
    server: {
      proxy: {
        '^/(config|health|ingest(?:/file|/google-drive)?|ask(?:/stream)?|documents|drive|auth)': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
