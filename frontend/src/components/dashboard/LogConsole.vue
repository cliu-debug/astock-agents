<template>
  <div class="log-console">
    <!-- 头部 -->
    <div class="console-header">
      <span class="console-title">📝 分析日志</span>
      <div class="console-actions">
        <button class="btn-icon" @click="handleClear" title="清空日志">🗑️</button>
        <button
          class="btn-icon"
          :class="{ active: autoScroll }"
          @click="toggleAutoScroll"
          title="自动滚动"
        >
          {{ autoScroll ? '🔒' : '🔓' }}
        </button>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="console-body" ref="bodyRef">
      <TransitionGroup name="log">
        <div
          v-for="log in visibleLogs"
          :key="log.id"
          class="log-entry"
          :class="`level-${log.level}`"
        >
          <span class="log-time">{{ log.timestamp }}</span>
          <span class="log-source" :style="{ color: getSourceColor(log.source) }">
            [{{ log.sourceName }}]
          </span>
          <span class="log-icon">{{ getLogIcon(log.level) }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </TransitionGroup>

      <!-- 打字指示器动画 -->
      <div v-if="isRunning" class="typing-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { LogLevel } from '@/types/agent'
import type { LogEntry, AgentType } from '@/types/agent'

const props = withDefaults(defineProps<{
  logs: LogEntry[]
  maxLogs?: number
  isRunning?: boolean
}>(), {
  maxLogs: 200,
  isRunning: false,
})

const emit = defineEmits<{
  (e: 'clear'): void
}>()

const bodyRef = ref<HTMLElement>()
const autoScroll = ref(true)

/** 截取最大日志数量 */
const visibleLogs = computed((): LogEntry[] => {
  return props.logs.slice(-props.maxLogs)
})

/** 日志变化时自动滚动到底部 */
watch(
  () => visibleLogs.value.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      scrollToBottom()
    }
  }
)

/** 滚动到底部 */
const scrollToBottom = (): void => {
  if (bodyRef.value) {
    bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  }
}

/** 清空日志 */
const handleClear = (): void => {
  emit('clear')
}

/** 切换自动滚动 */
const toggleAutoScroll = (): void => {
  autoScroll.value = !autoScroll.value
}

/** 获取来源对应颜色 */
const getSourceColor = (source: AgentType | 'system'): string => {
  const colors: Record<string, string> = {
    data_fetcher: '#06B6D4',
    technical: '#3B82F6',
    fundamental: '#8B5CF6',
    sentiment: '#EC4899',
    news: '#F97316',
    bull: '#22C55E',
    bear: '#EF4444',
    risk: '#EAB308',
    trader: '#6366F1',
    system: '#94A3B8',
  }
  return colors[source] || '#94A3B8'
}

/** 获取日志级别对应图标 */
const getLogIcon = (level: LogLevel): string => {
  const icons: Record<LogLevel, string> = {
    [LogLevel.DEBUG]: '🔍',
    [LogLevel.INFO]: 'ℹ️',
    [LogLevel.SUCCESS]: '✅',
    [LogLevel.WARNING]: '⚠️',
    [LogLevel.ERROR]: '❌',
  }
  return icons[level] || 'ℹ️'
}
</script>

<style scoped>
.log-console {
  background: #0D1117;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 头部 */
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.console-title {
  font-size: 14px;
  font-weight: 600;
  color: #F8FAFC;
}

.console-actions {
  display: flex;
  gap: 8px;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
  line-height: 1;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.1);
}

.btn-icon.active {
  background: rgba(59, 130, 246, 0.2);
}

/* 日志主体 */
.console-body {
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  flex: 1;
}

.console-body::-webkit-scrollbar {
  width: 6px;
}

.console-body::-webkit-scrollbar-track {
  background: transparent;
}

.console-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

/* 日志条目 */
.log-entry {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  align-items: flex-start;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-time {
  color: #64748B;
  flex-shrink: 0;
  font-size: 12px;
}

.log-source {
  flex-shrink: 0;
  font-weight: 500;
  font-size: 12px;
}

.log-icon {
  flex-shrink: 0;
  font-size: 12px;
  line-height: 1.6;
}

.log-message {
  color: #E2E8F0;
  word-break: break-word;
  font-size: 12px;
}

/* 日志级别颜色区分 */
.level-debug .log-message {
  color: #94A3B8;
}

.level-success .log-message {
  color: #22C55E;
}

.level-warning .log-message {
  color: #F59E0B;
}

.level-error .log-message {
  color: #EF4444;
}

/* 日志进入动画 */
.log-enter-active {
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
  align-items: center;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  background: #64748B;
  border-radius: 50%;
  animation: bounce 1.4s ease-in-out infinite;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
