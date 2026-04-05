<template>
  <div class="time-input-with-unit">
    <el-input-number
      v-model="displayValue"
      :min="1"
      :max="999"
      :controls="false"
      :disabled="props.disabled"
      style="width: 80px"
    />
    <el-select v-model="selectedUnit" :disabled="props.disabled" style="width: 90px; margin-left: 8px">
      <el-option label="秒" value="seconds" />
      <el-option label="分钟" value="minutes" />
      <el-option label="小时" value="hours" />
    </el-select>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: { type: Number, default: 300 },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const UNITS = { seconds: 1, minutes: 60, hours: 3600 };

const inferUnit = (seconds) => {
  if (seconds >= 3600 && seconds % 3600 === 0) return 'hours';
  if (seconds >= 60 && seconds % 60 === 0) return 'minutes';
  return 'seconds';
};

const selectedUnit = computed({
  get() { return inferUnit(props.modelValue || 300); },
  set(newUnit) {
    const currentDisplay = Math.round((props.modelValue || 300) / UNITS[selectedUnit.value]);
    emit('update:modelValue', currentDisplay * UNITS[newUnit]);
  }
});

const displayValue = computed({
  get() { return Math.round((props.modelValue || 300) / UNITS[selectedUnit.value]); },
  set(val) { emit('update:modelValue', val * UNITS[selectedUnit.value]); }
});
</script>

<style scoped>
.time-input-with-unit { display: flex; align-items: center; }
</style>
