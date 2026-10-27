<template>
  <div class="history-container">
    <div class="header">
      <el-button @click="$router.push('/')" text>
        <el-icon><ArrowLeft /></el-icon>
        返回首页
      </el-button>
      <h1>🗂️ 我的行程历史</h1>
      <el-button :icon="Refresh" text @click="loadTrips">刷新</el-button>
    </div>

    <div v-loading="loading" class="content">
      <el-empty v-if="!loading && trips.length === 0" description="暂无历史行程，去规划一次吧">
        <el-button type="primary" @click="$router.push('/')">开始规划</el-button>
      </el-empty>

      <div v-else class="trip-grid">
        <el-card
          v-for="t in trips"
          :key="t.id"
          class="trip-card"
          shadow="hover"
          @click="viewTrip(t)"
        >
          <div class="trip-title">
            <el-icon><Location /></el-icon>
            <span>{{ t.title || `${t.city}（${t.travel_days}天）` }}</span>
          </div>
          <div class="trip-meta">
            <el-tag size="small">{{ t.city }}</el-tag>
            <span class="trip-date">{{ t.start_date }} ~ {{ t.end_date }}</span>
          </div>
          <div class="trip-footer">
            <span class="trip-created">{{ formatDate(t.created_at) }}</span>
            <el-popconfirm title="确认删除该行程？" @confirm="removeTrip(t.id)">
              <template #reference>
                <el-button type="danger" size="small" text :icon="Delete" @click.stop>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Location, Delete } from '@element-plus/icons-vue'
import { useTripStore } from '@/stores/trip'
import { getTripHistory, getTripHistoryDetail, deleteTripHistory } from '@/services/api'
import type { TripHistoryItem } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const tripStore = useTripStore()

const trips = ref<TripHistoryItem[]>([])
const loading = ref(false)

async function loadTrips() {
  loading.value = true
  try {
    trips.value = await getTripHistory()
  } catch {
    ElMessage.error('加载历史行程失败')
  } finally {
    loading.value = false
  }
}

async function viewTrip(t: TripHistoryItem) {
  try {
    const detail = await getTripHistoryDetail(t.id)
    tripStore.setTripPlan(detail.result)
    tripStore.setSessionId(t.session_id)
    tripStore.setStatus('completed')
    router.push('/result')
  } catch {
    ElMessage.error('加载行程详情失败')
  }
}

async function removeTrip(id: number) {
  try {
    await deleteTripHistory(id)
    ElMessage.success('已删除')
    await loadTrips()
  } catch {
    ElMessage.error('删除失败')
  }
}

function formatDate(d: string) {
  return dayjs(d).format('YYYY-MM-DD HH:mm')
}

onMounted(loadTrips)
</script>

<style scoped>
.history-container {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1100px;
  margin: 0 auto 20px;
}
.header h1 {
  font-size: 22px;
  color: #303133;
}
.content {
  max-width: 1100px;
  margin: 0 auto;
}
.trip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.trip-card {
  cursor: pointer;
  border-radius: 10px;
  transition: transform 0.15s;
}
.trip-card:hover {
  transform: translateY(-2px);
}
.trip-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.trip-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.trip-date {
  color: #606266;
  font-size: 13px;
}
.trip-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #f0f0f0;
  padding-top: 10px;
}
.trip-created {
  color: #909399;
  font-size: 12px;
}
</style>
