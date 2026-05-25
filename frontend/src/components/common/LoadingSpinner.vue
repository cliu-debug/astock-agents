<template>
  <div class="loading-spinner" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 50 50"
      class="spinner-svg"
    >
      <circle
        cx="25"
        cy="25"
        r="20"
        fill="none"
        :stroke="color"
        stroke-width="4"
        stroke-linecap="round"
        class="spinner-circle"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: number
  color?: string
}>(), {
  size: 40,
  color: '#3B82F6',
})
</script>

<style scoped>
.loading-spinner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.spinner-svg {
  animation: rotate 1.4s linear infinite;
}

.spinner-circle {
  stroke-dasharray: 90, 150;
  stroke-dashoffset: 0;
  animation: dash 1.4s ease-in-out infinite;
  opacity: 0.8;
}

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}
</style>
