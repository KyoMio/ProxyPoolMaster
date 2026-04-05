<template>
  <div class="env-var-config">
    <el-table :data="envVarsList" size="small" border style="width: 100%">
      <el-table-column prop="key" label="变量名" min-width="150">
        <template #default="{ row, $index }">
          <el-input 
            v-model="row.key" 
            placeholder="VAR_NAME"
            :disabled="!row.isNew"
            size="small"
            @blur="emitUpdate"
          />
        </template>
      </el-table-column>
      
      <el-table-column prop="value" label="值" min-width="250">
        <template #default="{ row }">
          <el-input
            v-model="row.value"
            :type="row.isSecret ? 'password' : 'text'"
            :placeholder="row.isSecret ? '输入敏感值' : '输入值'"
            size="small"
            show-password
            @blur="emitUpdate"
          />
          <span v-if="row.isMask" class="mask-hint">
            保持不变请留空或输入 ********
          </span>
        </template>
      </el-table-column>
      
      <el-table-column prop="isSecret" label="敏感" width="80" align="center">
        <template #default="{ row }">
          <el-checkbox v-model="row.isSecret" @change="emitUpdate" />
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="80" align="center">
        <template #default="{ $index }">
          <el-button 
            type="danger" 
            size="small"
            circle
            @click="removeVar($index)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="env-var-actions">
      <el-button 
        type="primary" 
        plain
        size="small" 
        @click="addVar"
      >
        <el-icon><Plus /></el-icon>
        添加变量
      </el-button>
    </div>
    
    <el-alert
      v-if="hasSecretVars"
      type="info"
      :closable="false"
      size="small"
      class="env-var-hint"
    >
      <template #default>
        <el-icon><Lock /></el-icon>
        敏感变量（标记为 🔒）将被掩码显示，在日志中脱敏处理
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Delete, Plus, Lock } from '@element-plus/icons-vue'

interface EnvVarItem {
  key: string
  value: string
  isSecret: boolean
  isNew?: boolean
  isMask?: boolean
}

interface Props {
  modelValue: Record<string, { value: string; is_secret: boolean }>
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, { value: string; is_secret: boolean }>): void
}>()

// 内部状态，避免直接修改 props
const envVarsList = ref<EnvVarItem[]>([])

// 从 props 初始化数据
const initFromProps = () => {
  const result: EnvVarItem[] = []
  for (const [key, config] of Object.entries(props.modelValue || {})) {
    const isSecret = config?.is_secret || false
    const value = config?.value || ''
    result.push({
      key,
      value: isSecret ? '********' : value,
      isSecret,
      isMask: isSecret && value.length > 0,
      isNew: false
    })
  }
  envVarsList.value = result
}

// 监听 props 变化，重新初始化
watch(() => props.modelValue, initFromProps, { deep: true, immediate: true })

const hasSecretVars = computed(() => 
  envVarsList.value.some(v => v.isSecret)
)

// 触发更新到父组件
const emitUpdate = () => {
  const result: Record<string, { value: string; is_secret: boolean }> = {}
  for (const item of envVarsList.value) {
    if (item.key.trim()) {
      // 如果是掩码值且之前存在，保持原值
      let finalValue = item.value
      if (item.value === '********' && props.modelValue[item.key]) {
        finalValue = props.modelValue[item.key]?.value ?? finalValue
      }
      result[item.key] = {
        value: finalValue,
        is_secret: item.isSecret
      }
    }
  }
  emit('update:modelValue', result)
}

const addVar = () => {
  envVarsList.value.push({
    key: '',
    value: '',
    isSecret: false,
    isNew: true,
    isMask: false
  })
}

const removeVar = (index: number) => {
  envVarsList.value.splice(index, 1)
  emitUpdate()
}
</script>

<style scoped>
.env-var-config {
  width: 100%;
}

.env-var-actions {
  margin-top: 12px;
}

.env-var-hint {
  margin-top: 12px;
}

.mask-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  display: block;
}
</style>
