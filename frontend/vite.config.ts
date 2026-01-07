import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync } from 'fs'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'copy-static-config',
      closeBundle() {
        copyFileSync(
          resolve(__dirname, 'staticwebapp.config.json'),
          resolve(__dirname, 'dist/staticwebapp.config.json')
        )
      }
    }
  ],
  server: {
    port: 3000,
  },
})
