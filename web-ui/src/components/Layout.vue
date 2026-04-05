<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
      <div class="sidebar-header">
        <span v-show="!isCollapse" class="logo-text">ProxyPoolMaster</span>
        <span v-show="isCollapse" class="logo-icon" aria-label="ProxyPoolMaster">PPM</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/proxies">
          <el-icon><Connection /></el-icon>
          <template #title>代理列表</template>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <template #title>日志查看</template>
        </el-menu-item>
        <el-menu-item index="/config">
          <el-icon><Setting /></el-icon>
          <template #title>配置管理</template>
        </el-menu-item>
        <el-menu-item index="/system">
          <el-icon><Monitor /></el-icon>
          <template #title>系统状态</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-button
            :type="hasToken ? 'success' : 'danger'"
            :class="['token-btn', { 'token-configured': hasToken }]"
            @click="showTokenDialog"
          >
            <el-icon class="token-icon"><Lock /></el-icon>
            <span class="token-text">{{ hasToken ? 'Token 已配置' : '配置 Token' }}</span>
          </el-button>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

    <!-- Token 配置弹窗 -->
    <el-dialog
      v-model="tokenDialogVisible"
      title="🔐 API Token 配置"
      width="400px"
      :close-on-click-modal="false"
      class="token-dialog"
    >
      <el-form :model="tokenForm" label-position="top">
        <el-form-item label="API Token">
          <el-input
            v-model="tokenForm.token"
            type="password"
            show-password
            placeholder="请输入您的 API Token"
            clearable
          />
        </el-form-item>
        <el-form-item v-if="hasToken">
          <el-alert
            title="当前已配置 Token，保存新 Token 将覆盖原配置"
            type="info"
            :closable="false"
            show-icon
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button 
            v-if="hasToken" 
            type="danger" 
            plain 
            @click="clearToken"
          >
            清除 Token
          </el-button>
          <div class="dialog-footer-right">
            <el-button @click="tokenDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="saveToken" :disabled="!tokenForm.token.trim()">
              保存
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DataLine,
  Connection,
  Document,
  Setting,
  Monitor,
  Fold,
  Expand,
  Lock
} from '@element-plus/icons-vue'

const route = useRoute()

// 侧边栏折叠状态
const isCollapse = ref(false)
const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 页面标题
const pageTitle = computed(() => {
  const titles = {
    '/dashboard': '仪表盘',
    '/proxies': '代理列表',
    '/logs': '日志查看',
    '/config': '配置管理',
    '/system': '系统状态'
  }
  return titles[route.path] || 'ProxyPoolMaster'
})

// Token 状态
const hasToken = ref(false)
const tokenDialogVisible = ref(false)
const tokenForm = ref({
  token: ''
})

// 检查 Token 状态
const checkTokenStatus = () => {
  const token = localStorage.getItem('api_token')
  hasToken.value = !!token
}

// 显示 Token 弹窗
const showTokenDialog = () => {
  const currentToken = localStorage.getItem('api_token') || ''
  tokenForm.value.token = currentToken
  tokenDialogVisible.value = true
}

// 保存 Token
const saveToken = () => {
  const token = tokenForm.value.token.trim()
  if (!token) {
    ElMessage.warning('API Token 不能为空！')
    return
  }
  
  localStorage.setItem('api_token', token)
  hasToken.value = true
  tokenDialogVisible.value = false
  ElMessage.success('API Token 已保存！')
  
  // 触发页面刷新（如果当前在 dashboard）
  if (route.path === '/dashboard') {
    window.location.reload()
  }
}

// 清除 Token
const clearToken = () => {
  localStorage.removeItem('api_token')
  hasToken.value = false
  tokenForm.value.token = ''
  tokenDialogVisible.value = false
  ElMessage.info('API Token 已清除！')
  
  // 触发页面刷新（如果当前在 dashboard）
  if (route.path === '/dashboard') {
    window.location.reload()
  }
}

// 监听路由变化，检查 Token
watch(() => route.path, () => {
  checkTokenStatus()
})

onMounted(() => {
  checkTokenStatus()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

/* 侧边栏样式 */
.sidebar {
  background-color: #304156;
  transition: width 0.3s;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #1f2d3d;
}

.logo-text {
  color: #fff;
  font-size: 18px;
  font-weight: bold;
}

.logo-icon {
  color: #fff;
  font-size: 24px;
}

.sidebar-menu {
  border-right: none;
}

/* 顶部栏样式 */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  margin-right: 15px;
  color: #606266;
  transition: color 0.3s;
}

.collapse-btn:hover {
  color: #409EFF;
}

.page-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
}

.token-btn {
  display: flex;
  align-items: center;
  gap: 5px;
}

.token-icon {
  font-size: 14px;
}

.token-text {
  font-size: 13px;
}

/* 主内容区 */
.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}

/* Token 弹窗样式 */
:deep(.token-dialog .el-dialog__header) {
  border-bottom: 1px solid #e4e7ed;
  margin-right: 0;
  padding-bottom: 15px;
}

:deep(.token-dialog .el-dialog__body) {
  padding: 20px;
}

:deep(.token-dialog .el-dialog__footer) {
  border-top: 1px solid #e4e7ed;
  padding: 15px 20px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-footer-right {
  display: flex;
  gap: 10px;
}
</style>
