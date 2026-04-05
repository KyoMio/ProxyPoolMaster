<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { testApiConnection } from '@/api/apiClient'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

// State
const currentToken = ref('')
const newToken = ref('')
const showToken = ref(false)
const testing = ref(false)
const saving = ref(false)

// Computed
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const maskedToken = computed(() => {
  const token = currentToken.value
  if (!token) return '未设置'
  if (showToken.value) return token
  // 短token处理：显示前2位 + 圆点 + 后2位
  if (token.length <= 4) return '•'.repeat(token.length)
  return token.slice(0, 4) + '•'.repeat(Math.max(0, token.length - 8)) + token.slice(-4)
})

const canSave = computed(() => {
  return newToken.value.trim().length > 0
})

// Methods
function init() {
  // Read current token from localStorage
  currentToken.value = localStorage.getItem('api_token') || ''
  newToken.value = ''
  showToken.value = false
}

async function handleTest() {
  const token = newToken.value.trim()
  if (!token) {
    ElMessage.warning('请输入 Token')
    return
  }
  
  testing.value = true
  try {
    const result = await testApiConnection(token)
    if (result.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error('连接测试失败: ' + (result.message || '未知错误'))
    }
  } catch (error: any) {
    ElMessage.error('连接测试失败: ' + (error.message || '未知错误'))
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  const token = newToken.value.trim()
  if (!token) {
    ElMessage.warning('请输入 Token')
    return
  }
  
  saving.value = true
  try {
    // Save to localStorage
    localStorage.setItem('api_token', token)
    currentToken.value = token
    newToken.value = ''
    ElMessage.success('Token 已保存')
    visible.value = false
    // Reload page to apply new token
    window.location.reload()
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function handleCancel() {
  visible.value = false
}

// Watch dialog open
watch(() => props.modelValue, (val) => {
  if (val) init()
})
</script>

<template>
  <el-dialog
    v-model="visible"
    title="API Token 设置"
    width="400px"
    :close-on-click-modal="false"
  >
    <div class="token-dialog-content">
      <!-- Current Token -->
      <div class="form-item">
        <label>当前 Token:</label>
        <div class="current-token">
          <span class="token-text">{{ maskedToken }}</span>
          <el-button
            v-if="currentToken"
            link
            type="primary"
            size="small"
            @click="showToken = !showToken"
          >
            {{ showToken ? '隐藏' : '显示' }}
          </el-button>
        </div>
      </div>
      
      <!-- New Token Input -->
      <div class="form-item">
        <label>新 Token:</label>
        <el-input
          v-model="newToken"
          type="password"
          show-password
          placeholder="请输入新的 API Token"
          size="default"
        />
      </div>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button
          @click="handleTest"
          :loading="testing"
          :disabled="!canSave"
        >
          测试连接
        </el-button>
        <el-button @click="handleCancel">取消</el-button>
        <el-button
          type="primary"
          @click="handleSave"
          :loading="saving"
          :disabled="!canSave"
        >
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.token-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-item label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.current-token {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.token-text {
  font-family: monospace;
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
  word-break: break-all;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
