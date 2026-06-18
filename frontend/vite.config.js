import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const DEFAULTS = {
  REACT_APP_GW3_URL: 'http://localhost:8002',
  REACT_APP_BACKEND_URL: 'http://localhost:8001',
}

/** CRA-compatible process.env.REACT_APP_* injection for Vite. */
function reactAppDefine(mode) {
  const fileEnv = loadEnv(mode, __dirname, 'REACT_APP_')
  const define = {}

  const keys = new Set([
    ...Object.keys(DEFAULTS),
    ...Object.keys(fileEnv),
    ...Object.keys(process.env).filter((k) => k.startsWith('REACT_APP_')),
  ])

  for (const key of keys) {
    const value = process.env[key] ?? fileEnv[key] ?? DEFAULTS[key] ?? ''
    define[`process.env.${key}`] = JSON.stringify(value)
  }

  return define
}

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  root: './',
  publicDir: 'public',
  server: {
    port: 3000,
    open: true,
  },
  build: {
    outDir: 'build',
    sourcemap: false,
    emptyOutDir: true,
  },
  define: reactAppDefine(mode),
}))