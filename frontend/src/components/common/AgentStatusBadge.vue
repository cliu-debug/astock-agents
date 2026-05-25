<template>
  <span class="status-badge" :class="`status-${status}`" :style="{ color: statusColor }">
    <span class="status-dot" :style="{ background: statusColor }"></span>
    <span class="status-text">{{ statusText }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AgentStatus } from '@/types/agent'

const props = defineProps<{
  status: AgentStatus
}>()

/** 状态对应中文文本 */
const statusText = computed((): string => {
  const map: Record<AgentStatus, string> = {
    [AgentStatus.IDLE]: '空闲',
    [AgentStatus.INITIALIZING]: '初始化',
    [AgentStatus.RUNNING]: '运行中',
    [AgentStatus.WAITING]: '等待中',
    [AgentStatus.COMPLETED]: '已完成',
    [AgentStatus.FAILED]: '失败',
  }
  return map[props.status] || props.status
})

/** 状态对应颜色 */
const statusColor = computed((): string => {
  const map: Record<AgentStatus, string> = {
    [AgentStatus.IDLE]: '#10B981',
    [AgentStatus.INITIALIZING]: '#3B82F6',
    [AgentStatus.RUNNING]: '#F59E0B',
    [AgentStatus.WAITING]: '#8B5CF6',
    [AgentStatus.COMPLETED]: '#22C55E',
    [AgentStatus.FAILED]: '#EF4444',
  }
  return map[props.status] || '#64748B'
})
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.08);
  line-height: 1;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-text {
  white-space: nowrap;
}

.status-running .status-dot {
  animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
</style>
