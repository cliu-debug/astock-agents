<template>
  <div
    class="agent-card"
    :class="[`status-${agent.status}`, { 'is-active': isActive }]"
    @click="handleCardClick"
  >
    <!-- 头部：图标 + 名称 + 状态 -->
    <div class="agent-header">
      <div class="agent-icon" :style="{ background: agentColor }">
        {{ agent.icon }}
      </div>
      <div class="agent-info">
        <div class="agent-name">{{ agent.name }}</div>
        <AgentStatusBadge :status="agent.status" />
      </div>
    </div>

    <!-- 进度条（非 idle 时显示） -->
    <div class="agent-progress" v-if="agent.status !== AgentStatus.IDLE">
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: `${agent.progress}%`, background: agentColor }"
        ></div>
      </div>
      <span class="progress-text">{{ agent.progress }}%</span>
    </div>

    <!-- 当前任务描述 -->
    <div class="agent-task" v-if="agent.currentTask">
      <span class="task-icon">📌</span>
      <span class="task-text">{{ agent.currentTask }}</span>
    </div>

    <!-- 输出摘要（completed 时显示） -->
    <div class="agent-output" v-if="agent.output && agent.status === AgentStatus.COMPLETED">
      <div class="output-summary">{{ agent.output.summary }}</div>
      <div class="output-metrics" v-if="hasKeyMetrics">
        <span
          v-for="(value, key) in agent.output.keyMetrics"
          :key="key"
          class="metric-tag"
        >
          {{ key }}: {{ value }}
        </span>
      </div>
    </div>

    <!-- 运行中脉冲动画 -->
    <div class="running-animation" v-if="agent.status === AgentStatus.RUNNING">
      <div class="pulse-ring"></div>
      <div class="pulse-ring delay-1"></div>
      <div class="pulse-ring delay-2"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AgentStatus, AgentType } from '@/types/agent'
import type { Agent } from '@/types/agent'
import AgentStatusBadge from '@/components/common/AgentStatusBadge.vue'

const props = defineProps<{
  agent: Agent
}>()

const emit = defineEmits<{
  (e: 'click', agent: Agent): void
}>()

/** 根据 agent.type 获取对应颜色 */
const agentColor = computed((): string => {
  const colorMap: Record<AgentType, string> = {
    [AgentType.DATA_FETCHER]: '#06B6D4',
    [AgentType.TECHNICAL_ANALYST]: '#3B82F6',
    [AgentType.FUNDAMENTAL_ANALYST]: '#8B5CF6',
    [AgentType.SENTIMENT_ANALYST]: '#EC4899',
    [AgentType.NEWS_ANALYST]: '#F97316',
    [AgentType.BULL_RESEARCHER]: '#22C55E',
    [AgentType.BEAR_RESEARCHER]: '#EF4444',
    [AgentType.RISK_MANAGER]: '#EAB308',
    [AgentType.TRADER]: '#6366F1',
  }
  return colorMap[props.agent.type] || '#64748B'
})

/** 是否处于活跃状态 */
const isActive = computed((): boolean => {
  return props.agent.status === AgentStatus.RUNNING || props.agent.status === AgentStatus.INITIALIZING
})

/** 是否有关键指标数据 */
const hasKeyMetrics = computed((): boolean => {
  return !!props.agent.output?.keyMetrics && Object.keys(props.agent.output.keyMetrics).length > 0
})

/** 处理卡片点击事件 */
const handleCardClick = (): void => {
  emit('click', props.agent)
}
</script>

<style scoped>
.agent-card {
  background: #1E293B;
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid transparent;
  position: relative;
  overflow: hidden;
}

.agent-card:hover {
  transform: translateY(-4px);
  border-color: v-bind(agentColor);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.agent-card.status-running {
  border-color: v-bind(agentColor);
  box-shadow: 0 0 20px v-bind('agentColor + "40"');
}

.agent-card.status-completed {
  border-color: #22C55E;
}

.agent-card.status-failed {
  border-color: #EF4444;
}

/* 头部区域 */
.agent-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.agent-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: #F8FAFC;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 进度条 */
.agent-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: #94A3B8;
  flex-shrink: 0;
  min-width: 32px;
  text-align: right;
}

/* 当前任务 */
.agent-task {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.task-icon {
  flex-shrink: 0;
  font-size: 12px;
}

.task-text {
  font-size: 12px;
  color: #94A3B8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 输出摘要 */
.agent-output {
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.output-summary {
  font-size: 12px;
  color: #CBD5E1;
  line-height: 1.5;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.output-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.metric-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.08);
  color: #94A3B8;
  white-space: nowrap;
}

/* 脉冲动画 */
.running-animation {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.pulse-ring {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 16px;
  border: 2px solid v-bind(agentColor);
  animation: pulse 2s ease-out infinite;
  opacity: 0;
}

.pulse-ring.delay-1 {
  animation-delay: 0.5s;
}

.pulse-ring.delay-2 {
  animation-delay: 1s;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(1.05);
    opacity: 0;
  }
}
</style>
