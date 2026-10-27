<template>
  <div class="result-container">
    <!-- 头部 -->
    <div class="header">
      <el-button @click="$router.push('/')" text>
        <el-icon><ArrowLeft /></el-icon>
        返回首页
      </el-button>
      <h1>📋 行程规划结果</h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleExportPDF">
          <el-icon><Download /></el-icon>
          导出PDF
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重新规划
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="!tripPlan" class="empty-state">
      <el-empty description="暂无行程数据">
        <el-button type="primary" @click="$router.push('/')">开始规划</el-button>
      </el-empty>
    </div>

    <!-- 行程内容 -->
    <div v-else class="content">
      <!-- 概览卡片 -->
      <el-card class="overview-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Location /></el-icon>
            <span>行程概览</span>
          </div>
        </template>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="目的地">{{ tripPlan.city }}</el-descriptions-item>
          <el-descriptions-item label="出发日期">{{ tripPlan.start_date }}</el-descriptions-item>
          <el-descriptions-item label="返回日期">{{ tripPlan.end_date }}</el-descriptions-item>
          <el-descriptions-item label="行程天数">{{ tripPlan.days?.length || 0 }}天</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 天气预报卡片 -->
      <el-card v-if="tripPlan.weather_info && tripPlan.weather_info.length > 0" class="weather-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Cloudy /></el-icon>
            <span>天气预报</span>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col v-for="(weather, index) in tripPlan.weather_info" :key="index" :span="6">
            <div class="weather-item">
              <div class="weather-date">{{ weather.date }}</div>
              <div class="weather-icon">{{ getWeatherIcon(weather.day_weather) }}</div>
              <div class="weather-temp">
                <span class="temp-day">{{ weather.day_temp }}°</span>
                <span class="temp-divider">/</span>
                <span class="temp-night">{{ weather.night_temp }}°</span>
              </div>
              <div class="weather-desc">{{ weather.day_weather }}</div>
              <div class="weather-wind">{{ weather.wind_direction }} {{ weather.wind_power }}级</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 地图展示 -->
      <el-card class="map-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><MapLocation /></el-icon>
            <span>景点地图</span>
          </div>
        </template>
        <div id="map-container" class="map-container"></div>
      </el-card>

      <!-- 每日行程 -->
      <el-card class="itinerary-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Calendar /></el-icon>
            <span>每日行程</span>
          </div>
        </template>
        <el-collapse v-model="activeDays">
          <el-collapse-item
            v-for="(day, index) in tripPlan.days"
            :key="index"
            :name="index"
          >
            <template #title>
              <div class="day-title">
                <el-tag type="primary">第{{ day.day_index + 1 }}天</el-tag>
                <span class="day-date">{{ day.date }}</span>
                <span class="day-theme">{{ day.description }}</span>
              </div>
            </template>

            <!-- 天气建议 -->
            <div v-if="day.weather_advice" class="weather-advice-section">
              <el-alert
                :title="day.need_umbrella ? '🌤️ 今日天气提醒 - 建议带伞' : '🌤️ 今日天气提醒'"
                :description="day.weather_advice"
                :type="day.need_umbrella ? 'warning' : 'info'"
                :closable="false"
                show-icon
              >
                <template #default>
                  <div class="weather-detail">
                    {{ day.weather_advice }}
                    <span v-if="day.need_umbrella" class="umbrella-tip">
                      <el-icon><Umbrella /></el-icon> 请携带雨伞
                    </span>
                  </div>
                </template>
              </el-alert>
            </div>

            <!-- 景点列表 -->
            <el-timeline>
              <el-timeline-item
                v-for="(attraction, attrIndex) in day.attractions"
                :key="attrIndex"
                placement="top"
              >
                <el-card class="spot-card">
                  <div class="spot-header">
                    <h4>{{ attraction.name }}</h4>
                    <el-tag v-if="attraction.category" size="small">{{ attraction.category }}</el-tag>
                  </div>
                  <div class="spot-info">
                    <p v-if="attraction.description">{{ attraction.description }}</p>
                    <div class="spot-details">
                      <span v-if="attraction.visit_duration">
                        <el-icon><Clock /></el-icon>
                        游玩时长: {{ attraction.visit_duration }}分钟
                      </span>
                      <span v-if="attraction.ticket_price">
                        <el-icon><Ticket /></el-icon>
                        门票: ¥{{ attraction.ticket_price }}
                      </span>
                    </div>
                    <div class="spot-address">
                      <el-icon><Location /></el-icon>
                      {{ attraction.address }}
                    </div>
                  </div>
                </el-card>
              </el-timeline-item>
            </el-timeline>

            <!-- 餐饮推荐 -->
            <div v-if="day.meals && day.meals.length > 0" class="dining-section">
              <h4><el-icon><Food /></el-icon> 餐饮推荐</h4>
              <el-row :gutter="12">
                <el-col v-for="(meal, mealIndex) in day.meals" :key="mealIndex" :span="8">
                  <el-card shadow="hover" class="meal-card">
                    <div class="meal-type">{{ meal.type === 'breakfast' ? '早餐' : meal.type === 'lunch' ? '午餐' : '晚餐' }}</div>
                    <div class="meal-name">{{ meal.name }}</div>
                    <div class="meal-cuisine">{{ meal.description }}</div>
                    <div v-if="meal.estimated_cost" class="meal-price">预估: ¥{{ meal.estimated_cost }}</div>
                  </el-card>
                </el-col>
              </el-row>
            </div>

            <!-- 住宿信息 -->
            <div v-if="day.hotel" class="accommodation-section">
              <h4><el-icon><House /></el-icon> 住宿安排</h4>
              <el-card shadow="hover">
                <div class="hotel-info">
                  <div class="hotel-name">{{ day.hotel.name }}</div>
                  <div class="hotel-details">
                    <span v-if="day.hotel.type">{{ day.hotel.type }}</span>
                    <span v-if="day.hotel.price_range">{{ day.hotel.price_range }}</span>
                    <span v-if="day.hotel.rating">
                      <el-icon><Star /></el-icon>
                      {{ day.hotel.rating }}
                    </span>
                  </div>
                  <div v-if="day.hotel.address" class="hotel-address">
                    <el-icon><Location /></el-icon>
                    {{ day.hotel.address }}
                  </div>
                </div>
              </el-card>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 总预算 -->
      <el-card v-if="tripPlan.budget" class="budget-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Wallet /></el-icon>
            <span>预算估算</span>
          </div>
        </template>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-statistic title="景点门票" :value="tripPlan.budget.total_attractions" suffix="元" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="住宿费用" :value="tripPlan.budget.total_hotels" suffix="元" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="餐饮费用" :value="tripPlan.budget.total_meals" suffix="元" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="交通费用" :value="tripPlan.budget.total_transportation" suffix="元" />
          </el-col>
        </el-row>
        <el-divider />
        <el-statistic title="总预算" :value="tripPlan.budget.total" suffix="元" class="total-budget" />
      </el-card>

      <!-- 总体建议 -->
      <el-card v-if="tripPlan.overall_suggestions" class="tips-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Warning /></el-icon>
            <span>旅行建议</span>
          </div>
        </template>
        <p style="line-height: 1.8; color: #606266;">{{ tripPlan.overall_suggestions }}</p>
      </el-card>
    </div>

    <!-- 人工审核对话框 -->
    <el-dialog v-model="showReviewDialog" title="行程确认" width="800px" top="5vh">
      <div class="review-content">
        <!-- 重新规划进度 -->
        <div v-if="regenerating" class="regen-loading">
          <div class="regen-title">正在为您重新规划...</div>
          <el-progress :indeterminate="true" :show-text="false" :stroke-width="10" :percentage="100" />
          <div class="regen-tip">AI 正在根据您的修改意见重新编排行程，请稍候</div>
        </div>

        <template v-else>
        <el-alert
          title="请确认您的行程安排"
          type="warning"
          description="AI已为您生成行程规划，请滚动查看完整内容后确认。"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />

        <!-- 行程预览 - 可滚动 -->
        <div class="review-itinerary" v-if="tripPlan">
          <el-collapse v-model="activeDays">
            <el-collapse-item
              v-for="(day, index) in tripPlan.days"
              :key="index"
              :name="index"
            >
              <template #title>
                <div class="day-title">
                  <el-tag type="primary">第{{ day.day_index + 1 }}天</el-tag>
                  <span class="day-date">{{ day.date }}</span>
                </div>
              </template>

              <!-- 景点 -->
              <div class="review-section">
                <strong>📍 景点：</strong>
                <span v-for="(attr, idx) in day.attractions" :key="idx">
                  {{ attr.name }}{{ idx < day.attractions.length - 1 ? '、' : '' }}
                </span>
              </div>

              <!-- 餐饮 -->
              <div class="review-section" v-if="day.meals && day.meals.length > 0">
                <strong>🍜 餐饮：</strong>
                <div style="margin-left: 20px; margin-top: 4px;">
                  <span v-for="(meal, idx) in day.meals" :key="idx" class="meal-item">
                    <el-tag size="small" :type="meal.type === 'breakfast' ? 'success' : meal.type === 'lunch' ? 'warning' : 'danger'">
                      {{ meal.type === 'breakfast' ? '早餐' : meal.type === 'lunch' ? '午餐' : '晚餐' }}
                    </el-tag>
                    {{ meal.name }}
                  </span>
                </div>
              </div>

              <!-- 酒店/住宿 -->
              <div class="review-section review-hotel" v-if="day.hotel">
                <strong>🏨 住宿：</strong>
                <div style="margin-left: 20px; margin-top: 4px;">
                  <div class="hotel-name-review">{{ day.hotel.name }}</div>
                  <div class="hotel-address-review" v-if="day.hotel.address">
                    <el-icon><Location /></el-icon>
                    {{ day.hotel.address }}
                  </div>
                  <div class="hotel-info-review">
                    <span v-if="day.hotel.price_range">💰 {{ day.hotel.price_range }}</span>
                    <span v-if="day.hotel.rating" style="margin-left: 12px">
                      ⭐ {{ day.hotel.rating }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="review-section" v-else>
                <strong>🏨 住宿：</strong>
                <span class="no-hotel">暂无酒店信息</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div class="review-actions" style="margin-top: 16px">
          <el-input
            v-model="reviewComment"
            type="textarea"
            :rows="2"
            placeholder="如有修改意见，请在此输入（可选）..."
            :disabled="regenerating"
          />
        </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="handleReject" type="danger" :disabled="regenerating">
          <el-icon><Refresh /></el-icon>
          重新规划
        </el-button>
        <el-button type="primary" @click="handleApprove" :disabled="regenerating">
          <el-icon><Check /></el-icon>
          确认行程
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, Download, Refresh, Location, MapLocation, Calendar,
  Clock, Ticket, Star, Food, House, Wallet, Warning, Cloudy, Check, Umbrella
} from '@element-plus/icons-vue'
import { useTripStore } from '@/stores/trip'
import { approveTripPlan, rejectTripPlan, getStaticMapUrl } from '@/services/api'

const router = useRouter()
const tripStore = useTripStore()

const tripPlan = ref(tripStore.tripPlan)
const activeDays = ref<number[]>([0])
const showReviewDialog = ref(false)
const reviewComment = ref('')
const regenerating = ref(false)
const mapInstance = ref<any>(null)
const mapLoaded = ref(false)

// 根据天气描述获取对应图标
function getWeatherIcon(weather: string): string {
  if (!weather) return '🌤️'
  if (weather.includes('雨')) return '🌧️'
  if (weather.includes('雪')) return '❄️'
  if (weather.includes('云') || weather.includes('阴')) return '☁️'
  if (weather.includes('晴')) return '☀️'
  if (weather.includes('雾') || weather.includes('霾')) return '🌫️'
  if (weather.includes('风')) return '💨'
  return '🌤️'
}

// 初始化地图
async function initMap() {
  if (!tripPlan.value?.city) {
    console.log('[Map] 没有城市信息，跳过地图初始化')
    return
  }

  console.log('[Map] 开始初始化地图，城市:', tripPlan.value.city)

  await nextTick()

  const container = document.getElementById('map-container')
  if (!container) {
    console.error('[Map] 找不到地图容器')
    return
  }

  console.log('[Map] 地图容器已找到, offsetWidth:', container.offsetWidth, 'offsetHeight:', container.offsetHeight)

  const amapKey = import.meta.env.VITE_AMAP_KEY
  console.log('[Map] 高德地图 Key:', amapKey ? amapKey.substring(0, 8) + '...' : '未配置')

  if (!amapKey) {
    console.error('[Map] 高德地图 API Key 未配置')
    return
  }

  try {
    // 动态加载高德地图
    const AMap = (window as any).AMap
    if (!AMap) {
      console.log('[Map] 加载高德地图脚本...')
      const script = document.createElement('script')
      // 使用1.4版本，更稳定，不需要安全密钥
      script.src = `https://webapi.amap.com/maps?v=1.4.15&key=${amapKey}&plugin=AMap.Geocoder,AMap.Scale,AMap.ToolBar`
      script.onload = () => {
        console.log('[Map] 高德地图脚本加载成功')
        mapLoaded.value = true
        // 等待DOM更新后创建地图
        setTimeout(() => createMap(), 100)
      }
      script.onerror = (e) => {
        console.error('[Map] 高德地图脚本加载失败:', e)
      }
      document.head.appendChild(script)
    } else {
      console.log('[Map] 高德地图已存在')
      mapLoaded.value = true
      createMap()
    }
  } catch (error) {
    console.error('[Map] 地图初始化失败:', error)
  }
}

function createMap() {
  const AMap = (window as any).AMap
  if (!AMap) {
    console.error('[Map] AMap 未定义')
    return
  }

  if (!tripPlan.value) {
    console.error('[Map] tripPlan 未定义')
    return
  }

  console.log('[Map] 创建地图实例...')
  console.log('[Map] tripPlan数据:', JSON.stringify(tripPlan.value, null, 2))

  // 先获取城市坐标，然后创建地图
  const city = tripPlan.value.city
  console.log('[Map] 目标城市:', city)

  const geocoder = new AMap.Geocoder()

  // 先获取城市坐标
  geocoder.getLocation(city, (status: string, result: any) => {
    console.log('[Map] 地理编码结果:', status, result)

    let cityCenter = [116.397428, 39.90923] // 默认北京

    if (status === 'complete' && result.geocodes && result.geocodes.length > 0) {
      const location = result.geocodes[0].location
      cityCenter = [location.lng, location.lat]
      console.log('[Map] 城市中心坐标:', cityCenter)
    } else {
      console.warn('[Map] 未找到城市坐标，使用默认值')
    }

    // 创建地图实例 - 使用城市中心坐标
    const map = new AMap.Map('map-container', {
      resizeEnable: true,
      zoom: 12,
      center: cityCenter
    })

    // 添加地图控件
    AMap.plugin(['AMap.Scale', 'AMap.ToolBar'], function() {
      map.addControl(new AMap.Scale())
      map.addControl(new AMap.ToolBar())
    })

    mapInstance.value = map
    console.log('[Map] 地图实例创建成功，中心点:', cityCenter)

    // 收集所有景点坐标
    const markers: any[] = []
    console.log('[Map] 遍历景点数据...')

    tripPlan.value.days?.forEach((day: any, dayIndex: number) => {
      console.log(`[Map] 第${dayIndex + 1}天景点:`, day.attractions)
      day.attractions?.forEach((attraction: any, attrIndex: number) => {
        console.log(`[Map] 景点[${attrIndex}]:`, attraction.name, 'location:', attraction.location)
        if (attraction.location) {
          const lng = attraction.location.longitude || attraction.location.lng
          const lat = attraction.location.latitude || attraction.location.lat

          console.log(`[Map] 坐标: lng=${lng}, lat=${lat}`)

          if (lng && lat && lng !== 0 && lat !== 0) {
            console.log(`[Map] 添加标记: ${attraction.name} (${lng}, ${lat})`)

            // 创建标记
            const marker = new AMap.Marker({
              position: [lng, lat],
              title: attraction.name
            })

            // 添加点击事件显示名称
            marker.on('click', () => {
              const infoWindow = new AMap.InfoWindow({
                content: `<div style="padding:10px;"><strong>${attraction.name}</strong><br/>${attraction.address || ''}</div>`,
                offset: new AMap.Pixel(0, -30)
              })
              infoWindow.open(map, marker.getPosition())
            })

            markers.push(marker)
            map.add(marker)
          } else {
            console.warn(`[Map] 景点 ${attraction.name} 坐标无效`)
          }
        } else {
          console.warn(`[Map] 景点 ${attraction.name} 没有location字段`)
        }
      })
    })

    console.log('[Map] 共添加', markers.length, '个标记')

    // 如果有标记，自适应显示
    if (markers.length > 0) {
      map.setFitView(markers)
      console.log('[Map] 已调整视野以显示所有标记')
    }
  })
}

// 导出PDF
async function handleExportPDF() {
  ElMessage.info('正在生成PDF...')

  try {
    // 使用 html2canvas 和 jspdf
    const html2canvas = (await import('html2canvas')).default
    const { jsPDF } = await import('jspdf')

    const element = document.querySelector('.content') as HTMLElement
    if (!element) return

    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      logging: false
    })

    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF('p', 'mm', 'a4')
    const imgWidth = 210
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight)
    pdf.save(`${tripPlan.value?.city}旅行计划.pdf`)

    ElMessage.success('PDF导出成功')
  } catch (error) {
    console.error('PDF导出失败:', error)
    ElMessage.error('PDF导出失败')
  }
}

// 重新规划
function handleReset() {
  tripStore.reset()
  router.push('/')
}

// 确认行程
async function handleApprove() {
  if (!tripStore.sessionId) return

  try {
    const result = await approveTripPlan(tripStore.sessionId, reviewComment.value)
    ElMessage.success('行程已确认')
    showReviewDialog.value = false
    tripStore.setNeedHumanReview(false)
  } catch (error) {
    ElMessage.error('确认失败')
  }
}

// 拒绝行程（带意见重新规划）
async function handleReject() {
  if (!tripStore.sessionId || regenerating.value) return

  regenerating.value = true

  try {
    const result = await rejectTripPlan(tripStore.sessionId, reviewComment.value)

    if (result.success && result.data) {
      // 收到重新生成的行程 → 保持审核弹窗打开，让用户再次审核（不直接确认）
      tripPlan.value = result.data
      tripStore.setTripPlan(result.data)
      tripStore.setNeedHumanReview(true)
      reviewComment.value = ''
      activeDays.value = [0]
      ElMessage.success('已重新生成行程，请再次审核')
    } else if (result.status === 'max_retries_exceeded') {
      // 达到最大重试次数
      ElMessage.warning(result.message || '已达到最大重试次数，建议返回首页重新规划')
      showReviewDialog.value = false
      tripStore.reset()
      router.push('/')
    } else {
      // 其他失败情况，返回首页重新规划
      showReviewDialog.value = false
      router.push('/')
    }
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    regenerating.value = false
  }
}

onMounted(() => {
  console.log('[Result] onMounted')
  console.log('[Result] tripStore.needHumanReview:', tripStore.needHumanReview)
  console.log('[Result] tripPlan.value:', tripPlan.value)

  if (tripStore.needHumanReview) {
    showReviewDialog.value = true
  }

  // 延迟初始化地图，确保 DOM 已渲染
  setTimeout(() => {
    if (tripPlan.value) {
      console.log('[Result] 开始初始化地图')
      initMap()
    } else {
      console.log('[Result] 没有 tripPlan，跳过地图初始化')
    }
  }, 300)  // 增加延迟时间
})
</script>

<style scoped>
.result-container {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.header h1 {
  font-size: 24px;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
}

.map-container {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  background-color: #f5f5f5;
}

.weather-card {
  margin-bottom: 20px;
}

.weather-item {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.weather-date {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.weather-icon {
  font-size: 36px;
  margin: 8px 0;
}

.weather-temp {
  font-size: 20px;
  font-weight: 600;
  margin: 8px 0;
}

.temp-day {
  font-size: 24px;
}

.temp-divider {
  margin: 0 4px;
  opacity: 0.7;
}

.temp-night {
  font-size: 16px;
  opacity: 0.8;
}

.weather-desc {
  font-size: 14px;
  margin-top: 4px;
}

.weather-wind {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 4px;
}

.day-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.day-date {
  color: #909399;
  font-size: 14px;
}

.day-theme {
  font-weight: 500;
}

.weather-advice-section {
  margin-bottom: 16px;
}

.weather-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.umbrella-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #e6a23c;
  font-weight: 500;
}

.weather-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: #f0f9ff;
  border-radius: 4px;
  margin-bottom: 16px;
}

.spot-card {
  margin-bottom: 10px;
}

.spot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.spot-header h4 {
  margin: 0;
}

.spot-info p {
  color: #606266;
  margin-bottom: 8px;
}

.spot-details {
  display: flex;
  gap: 16px;
  color: #909399;
  font-size: 13px;
}

.spot-details span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.spot-tips {
  margin-top: 8px;
  padding: 8px;
  background: #fdf6ec;
  border-radius: 4px;
  font-size: 13px;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 4px;
}

.dining-section, .accommodation-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.dining-section h4, .accommodation-section h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.meal-card {
  text-align: center;
}

.meal-type {
  font-size: 12px;
  color: #909399;
}

.meal-name {
  font-weight: 600;
  margin: 4px 0;
}

.meal-cuisine {
  font-size: 13px;
  color: #606266;
}

.meal-price {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
}

.hotel-info {
  padding: 10px;
}

.hotel-name {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 8px;
}

.hotel-details {
  display: flex;
  gap: 16px;
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}

.hotel-address {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #606266;
  font-size: 13px;
}

.budget-card .el-row {
  text-align: center;
}

.total-budget {
  text-align: center;
}

.total-budget :deep(.el-statistic__number) {
  font-size: 32px;
  color: #409eff;
}

.review-content {
  padding: 0;
}

.review-itinerary {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}

.review-section {
  padding: 8px 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
}

.review-section strong {
  color: #303133;
  margin-right: 8px;
}

.review-hotel {
  background: #f0f9ff;
  padding: 12px;
  border-radius: 8px;
  margin: 8px 0;
}

.hotel-name-review {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}

.hotel-address-review {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.hotel-info-review {
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
}

.meal-item {
  display: inline-block;
  margin-right: 12px;
  margin-bottom: 4px;
}

.no-hotel {
  color: #909399;
  font-style: italic;
}

.review-actions {
  margin-top: 16px;
}

.regen-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  text-align: center;
}

.regen-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 20px;
}

.regen-loading :deep(.el-progress) {
  width: 280px;
  max-width: 80%;
}

.regen-tip {
  margin-top: 16px;
  font-size: 13px;
  color: #909399;
}
</style>
