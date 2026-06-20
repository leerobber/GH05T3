import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
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
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Vite 8 / rolldown requires the function form of manualChunks.
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/react-router')) return 'vendor-react'
          if (id.match(/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/)) return 'vendor-react'
          if (id.includes('@radix-ui')) return 'vendor-radix'
          if (id.includes('recharts') || id.includes('d3-')) return 'vendor-charts'
          if (id.includes('react-markdown') || id.includes('remark-') || id.includes('micromark')) return 'vendor-markdown'
          if (id.includes('lucide-react')) return 'vendor-icons'
          if (id.includes('react-hook-form') || id.includes('@hookform') || id.includes('zod')) return 'vendor-forms'
          if (id.includes('embla-carousel') || id.includes('react-day-picker') || id.includes('vaul')) return 'vendor-widgets'
          if (
            id.includes('axios') || id.includes('clsx') || id.includes('tailwind-merge') ||
            id.includes('date-fns') || id.includes('sonner') || id.includes('cmdk') ||
            id.includes('class-variance-authority') || id.includes('next-themes')
          ) return 'vendor-utils'
        },
      },
    },
  },
  define: {
    'process.env.REACT_APP_GW3_URL': JSON.stringify(process.env.REACT_APP_GW3_URL || 'http://localhost:8002'),
    'process.env.REACT_APP_BACKEND_URL': JSON.stringify(process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'),
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
  },
})
