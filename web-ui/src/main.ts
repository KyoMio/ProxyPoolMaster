import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/theme'

// Import global styles
import './styles/variables.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// Initialize theme after pinia is installed
const themeStore = useThemeStore()
themeStore.initTheme()

app.mount('#app')
