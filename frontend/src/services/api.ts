import { apiClient, getToken, setToken, clearToken, API_BASE_URL } from '@/utils/request'
import type {
  TripRequest,
  TripPlanResponse,
  StreamingResponse,
  ChatMessage,
  ChatResponse,
  UserFeedback,
  TripPlan,
  User,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  TripHistoryItem,
  TripHistoryDetail
} from '@/types'

// Token 管理、axios 实例、API 地址统一在 @/utils/request 中维护
// 此处重新导出，便于既有调用方 `from '@/services/api'` 继续使用
export { getToken, setToken, clearToken, API_BASE_URL }

// ===========================================
// 旅行规划 API
// ===========================================

/**
 * 创建旅行计划（同步）
 */
export async function createTripPlan(request: TripRequest): Promise<any> {
  const response = await apiClient.post('/api/trip/plan', request)
  return response.data
}

/**
 * 创建旅行计划（流式）
 */
export async function createTripPlanStream(
  request: TripRequest,
  onMessage: (data: StreamingResponse) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> {
  const baseUrl = API_BASE_URL
  const token = getToken()
  const response = await fetch(`${baseUrl}/api/trip/plan/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(request)
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamingResponse
            onMessage(data)
          } catch (e) {
            console.error('Failed to parse SSE data:', e)
          }
        }
      }
    }
  } catch (error) {
    onError(error as Error)
  } finally {
    onComplete()
  }
}

/**
 * 提交用户反馈
 */
export async function submitFeedback(feedback: UserFeedback): Promise<{
  success: boolean
  message: string
  status?: string
  action?: string
  data?: TripPlan
  retry_count?: number
}> {
  const response = await apiClient.post('/api/trip/feedback', feedback)
  return response.data
}

/**
 * 批准行程计划
 */
export async function approveTripPlan(sessionId: string, comment?: string): Promise<{ success: boolean; message: string }> {
  return submitFeedback({
    session_id: sessionId,
    action: 'approve',
    comment
  })
}

/**
 * 拒绝行程计划
 */
export async function rejectTripPlan(sessionId: string, comment?: string): Promise<{
  success: boolean
  message: string
  status?: string
  action?: string
  data?: TripPlan
  retry_count?: number
}> {
  return submitFeedback({
    session_id: sessionId,
    action: 'reject',
    comment
  })
}

/**
 * 获取旅行计划状态
 */
export async function getTripStatus(sessionId: string): Promise<{
  session_id: string
  status: string
  current_node: string
  steps: unknown[]
  errors: string[]
}> {
  const response = await apiClient.get(`/api/trip/status/${sessionId}`)
  return response.data
}

/**
 * 获取旅行计划结果
 */
export async function getTripResult(sessionId: string): Promise<TripPlanResponse> {
  const response = await apiClient.get<TripPlanResponse>(`/api/trip/result/${sessionId}`)
  return response.data
}

// ===========================================
// 多轮对话 API
// ===========================================

/**
 * 发送聊天消息
 */
export async function sendChatMessage(request: ChatMessage): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/api/chat/message', request)
  return response.data
}

/**
 * 获取对话历史
 */
export async function getChatHistory(sessionId: string): Promise<{
  session_id: string
  history: Array<{ role: string; content: string }>
}> {
  const response = await apiClient.get(`/api/chat/history/${sessionId}`)
  return response.data
}

/**
 * 清空对话历史
 */
export async function clearChatHistory(sessionId: string): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/api/chat/history/${sessionId}`)
  return response.data
}

// ===========================================
// 地图服务 API
// ===========================================

/**
 * 搜索 POI
 */
export async function searchPOI(keywords: string, city: string): Promise<{ success: boolean; data: unknown[] }> {
  const response = await apiClient.get('/api/map/poi', { params: { keywords, city } })
  return response.data
}

/**
 * 获取天气
 */
export async function getWeather(city: string): Promise<{ success: boolean; data: unknown[] }> {
  const response = await apiClient.get('/api/map/weather', { params: { city } })
  return response.data
}

/**
 * 获取静态地图图片
 */
export function getStaticMapUrl(city: string, markers?: string): string {
  const baseUrl = API_BASE_URL
  let url = `${baseUrl}/api/map/staticmap?city=${encodeURIComponent(city)}`
  if (markers) {
    url += `&markers=${encodeURIComponent(markers)}`
  }
  return url
}

// ===========================================
// 系统配置 API
// ===========================================

/**
 * 获取可用的 LLM 提供商
 */
export async function getLLMProviders(): Promise<{
  current: string
  available: Array<{ name: string; model: string }>
}> {
  const response = await apiClient.get('/api/config/llm-providers')
  return response.data
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<{ status: string }> {
  const response = await apiClient.get('/health')
  return response.data
}

// ===========================================
// 认证 API
// ===========================================

/**
 * 注册
 */
export async function register(data: RegisterRequest): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/auth/register', data)
  return response.data
}

/**
 * 登录
 */
export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/auth/login', data)
  return response.data
}

/**
 * 获取当前用户
 */
export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/api/auth/me')
  return response.data
}

// ===========================================
// 历史行程 API
// ===========================================

/**
 * 获取历史行程列表
 */
export async function getTripHistory(): Promise<TripHistoryItem[]> {
  const response = await apiClient.get<TripHistoryItem[]>('/api/user/trips')
  return response.data
}

/**
 * 获取历史行程详情
 */
export async function getTripHistoryDetail(id: number): Promise<TripHistoryDetail> {
  const response = await apiClient.get<TripHistoryDetail>(`/api/user/trips/${id}`)
  return response.data
}

/**
 * 删除历史行程
 */
export async function deleteTripHistory(id: number): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/api/user/trips/${id}`)
  return response.data
}

export default apiClient
