import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  register as apiRegister,
  getMe,
  getToken,
  setToken,
  clearToken
} from '@/services/api'
import type { User, LoginRequest, RegisterRequest } from '@/types'
import { useTripStore } from '@/stores/trip'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(data: LoginRequest) {
    const res = await apiLogin(data)
    token.value = res.access_token
    setToken(res.access_token)
    user.value = res.user
    return res
  }

  async function register(data: RegisterRequest) {
    const res = await apiRegister(data)
    token.value = res.access_token
    setToken(res.access_token)
    user.value = res.user
    return res
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const u = await getMe()
      user.value = u
      return u
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    token.value = null
    user.value = null
    clearToken()
    // 清空当前行程状态
    const tripStore = useTripStore()
    tripStore.reset()
  }

  return { token, user, isAuthenticated, login, register, fetchMe, logout }
})
