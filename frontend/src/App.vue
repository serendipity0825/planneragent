<template>
  <el-config-provider :locale="zhCn">
    <div class="app-layout">
      <nav v-if="showNav" class="navbar">
        <div class="nav-brand" @click="router.push('/')">🌍 智能旅行助手</div>
        <div class="nav-links">
          <el-button text @click="router.push('/')">规划行程</el-button>
          <el-button text @click="router.push('/history')">历史行程</el-button>
          <el-dropdown>
            <span class="user-chip">
              <el-icon><UserFilled /></el-icon>
              {{ authStore.user?.username || '用户' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </nav>
      <router-view />
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElConfigProvider } from 'element-plus'
import { UserFilled, ArrowDown, SwitchButton } from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const showNav = computed(() => !!route.meta.requiresAuth && authStore.isAuthenticated)

onMounted(async () => {
  // 启动时若有 token 但尚未加载用户信息，则拉取一次
  if (authStore.isAuthenticated && !authStore.user) {
    await authStore.fetchMe()
  }
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f7fa;
}

#app {
  min-height: 100vh;
}

.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  cursor: pointer;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  color: #606266;
  font-size: 14px;
}

.user-chip:hover {
  background: #f5f7fa;
}
</style>
