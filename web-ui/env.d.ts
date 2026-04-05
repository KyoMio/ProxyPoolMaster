/// <reference types="vite/client" />

declare const __APP_RELEASE_VERSION__: string
declare const __APP_GIT_SHA__: string

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}
