import { execSync } from 'node:child_process'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

const resolveGitSha = (): string => {
  const injectedSha = process.env.APP_GIT_SHA?.trim()
  if (injectedSha) {
    return injectedSha
  }

  try {
    return execSync('git rev-parse --short HEAD', {
      cwd: fileURLToPath(new URL('..', import.meta.url)),
      encoding: 'utf-8',
    }).trim()
  } catch {
    return 'unknown'
  }
}

const appReleaseVersion = process.env.APP_RELEASE_VERSION?.trim() || ''
const appGitSha = resolveGitSha()

// https://vite.dev/config/
export default defineConfig({
  define: {
    __APP_RELEASE_VERSION__: JSON.stringify(appReleaseVersion),
    __APP_GIT_SHA__: JSON.stringify(appGitSha),
  },
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API requests to backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Proxy WebSocket requests to backend
      '/ws': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
