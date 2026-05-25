<template>
  <div class="progress-ring" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <!-- 背景圆环 -->
      <circle
        class="progress-ring-bg"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="rgba(255, 255, 255, 0.1)"
        :stroke-width="strokeWidth"
      />
      <!-- 进度圆环 -->
      <circle
        class="progress-ring-fill"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :stroke="color"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        :style="{ transition: 'stroke-dashoffset 0.6s ease' }"
        :transform="`rotate(-90 ${size / 2} ${size / 2})`"
      />
    </svg>
    <!-- 百分比文字 -->
    <span class="progress-ring-text" :style="{ fontSize: `${size * 0.22}px` }">
      {{ Math.round(progress) }}%
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  progress: number
  color?: string
  size?: number
  strokeWidth?: number
}>(), {
  color: '#3B82F6',
  size: 60,
  strokeWidth: 8,
})

/** 圆环半径 */
const radius = computed((): number => {
  return (props.size - props.strokeWidth) / 2
})

/** 圆环周长 */
const circumference = computed((): number => {
  return 2 * Math.PI * radius.value
})

/** 进度偏移量 */
const dashOffset = computed((): number => {
  const clampedProgress = Math.max(0, Math.min(100, props.progress))
  return circumference.value * (1 - clampedProgress / 100)
})
</script>

<style scoped>
.progress-ring {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.progress-ring-fill {
  transition: stroke-dashoffset 0.6s ease;
}

.progress-ring-text {
  position: absolute;
  font-weight: 600;
  color: #F8FAFC;
  line-height: 1;
}
</style>
