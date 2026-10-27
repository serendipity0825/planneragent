import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import Home from './views/Home.vue'
import Result from './views/Result.vue'
import Chat from './views/Chat.vue'
import Login from './views/Login.vue'
import History from './views/History.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Home', component: Home, meta: { requiresAuth: true } },
    { path: '/result', name: 'Result', component: Result, meta: { requiresAuth: true } },
    { path: '/chat', name: 'Chat', component: Chat, meta: { requiresAuth: true } },
    { path: '/history', name: 'History', component: History, meta: { requiresAuth: true } },
    { path: '/login', name: 'Login', component: Login },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

// 路由守卫：未登录访问受保护页面 → 跳转登录；已登录访问登录页 → 跳转首页
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('trip_token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.name === 'Login' && token) {
    next('/')
  } else {
    next()
  }
})

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
