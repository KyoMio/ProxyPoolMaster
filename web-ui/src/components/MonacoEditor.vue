<template>
  <div ref="editorContainer" class="monaco-editor-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as monaco from 'monaco-editor'

interface Props {
  modelValue: string
  language?: string
  theme?: 'vs' | 'vs-dark' | 'hc-black'
  height?: string
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  language: 'python',
  theme: 'vs',
  height: '400px',
  readonly: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

const editorContainer = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | null = null

onMounted(() => {
  if (!editorContainer.value) return
  
  // 创建编辑器实例
  editor = monaco.editor.create(editorContainer.value, {
    value: props.modelValue,
    language: props.language,
    theme: props.theme,
    automaticLayout: true,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 14,
    lineNumbers: 'on',
    roundedSelection: false,
    scrollbar: {
      useShadows: false,
      verticalHasArrows: true,
      horizontalHasArrows: true,
      vertical: 'auto',
      horizontal: 'auto'
    },
    readOnly: props.readonly,
    wordWrap: 'on',
    folding: true,
    renderLineHighlight: 'line',
    matchBrackets: 'always'
  })
  
  // 监听内容变化
  editor.onDidChangeModelContent(() => {
    const value = editor?.getValue() || ''
    emit('update:modelValue', value)
    emit('change', value)
  })
})

// 监听外部值变化
watch(() => props.modelValue, (newValue) => {
  if (editor && editor.getValue() !== newValue) {
    editor.setValue(newValue)
  }
})

// 监听主题变化
watch(() => props.theme, (newTheme) => {
  if (editor) {
    monaco.editor.setTheme(newTheme)
  }
})

// 监听只读状态变化
watch(() => props.readonly, (newValue) => {
  if (editor) {
    editor.updateOptions({ readOnly: newValue })
  }
})

onBeforeUnmount(() => {
  if (editor) {
    editor.dispose()
    editor = null
  }
})

// 暴露方法给父组件
defineExpose({
  getEditor: () => editor,
  formatCode: () => {
    editor?.getAction('editor.action.formatDocument')?.run()
  }
})
</script>

<style scoped>
.monaco-editor-container {
  width: 100%;
  height: v-bind('props.height');
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}
</style>
