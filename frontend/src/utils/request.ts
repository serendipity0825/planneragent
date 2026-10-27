import axios from 'axios'

/**
 * 统一请求封装
 *
 * 地址策略：
 * - 开发环境 / CloudStudio 代理模式 → 留空（走相对路径，由 Vite 的 /api 代理转发到后端 8000）
 * - 生产部署 → 通过环境变量 VITE_API_BASE_URL 指定后端地址，兜底 http://localhost:8000
 *
 * 注意：本项目接口路径本身已带 /api 前缀（如 /api/trip/plan），
 * 因此 baseURL 不能再写成 /api 或 /api/v1，否则会拼成 /api/api/...。
 */
const API_BASE_URL: string = import.meta.env.DEV
  ? ''
  : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')

if (import.meta.env.DEV) {
  console.log('[request] API_BASE_URL:', API_BASE_URL || '使用 Vite 代理（相对路径）')
}

// ===========================================
// Token 管理（与原有 auth 流程保持同一 key）
// ===========================================
const TOKEN_KEY = 'trip_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * fetch / SSE 等非 axios 场景使用的基础地址。
 * 开发期为空字符串（相对路径走代理），生产期为完整后端地址。
 */
export function getBaseUrl(): string {
  return API_BASE_URL
}

// ===========================================
// axios 实例
// ===========================================
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 分钟，旅行规划为长任务
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：注入鉴权头 + 调试日志
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    if (import.meta.env.DEV) {
      console.log('API Request:', config.method?.toUpperCase(), (config.baseURL ?? '') + (config.url ?? ''), config.data)
    }
    return config
  },
  (error) => {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器：处理 401 + 调试日志
apiClient.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.log('API Response:', response.status, response.data)
    }
    return response
  },
  (error) => {
    console.error('API Response Error:', error.response?.status, error.response?.data || error.message)
    // 401：清除 token 并跳转登录页
    if (error.response?.status === 401) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export { apiClient, API_BASE_URL }
export default apiClient
