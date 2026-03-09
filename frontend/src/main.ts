import { createApp } from 'vue'
import { createDiscreteApi, darkTheme } from 'naive-ui'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(router)
app.mount('#app')

const { message } = createDiscreteApi(['message'], {
  configProviderProps: {
    theme: darkTheme,
  },
})

window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason as Error
  if (error?.message) {
    message.error(error.message)
  }
})
