<template>
  <g
    class="workflow-node"
    :class="{
      'is-active': isActive,
      'is-completed': isCompleted,
      'is-pending': !isActive && !isCompleted,
    }"
    :transform="`translate(${x}, ${y})`"
  >
    <circle
      class="node-bg"
      cx="0" cy="0" r="32"
    />
    <circle
      class="node-ring"
      cx="0" cy="0" r="32"
    />
    <circle
      v-if="isActive"
      class="node-pulse"
      cx="0" cy="0" r="32"
    />

    <text class="node-icon" x="0" y="-2" text-anchor="middle" dominant-baseline="central">
      {{ statusIcon }}
    </text>

    <text class="node-name" x="0" y="50" text-anchor="middle" dominant-baseline="central">
      {{ phase.name }}
    </text>

    <g class="agent-icons" :transform="`translate(0, 72)`">
      <text
        v-for="(agentType, idx) in phase.agents"
        :key="agentType"
        class="agent-icon-item"
        :x="(idx - (phase.agents.length - 1) / 2) * 22"
        y="0"
        text-anchor="middle"
        dominant-baseline="central"
      >
        {{ agentIconMap[agentType] || '🤖' }}
      </text>
    </g>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AgentType } from '@/types/agent'
import type { WorkflowPhase } from '@/types/agent'

const props = defineProps<{
  /** 工作流阶段数据 */
  phase: WorkflowPhase
  /** 是否为当前激活阶段 */
  isActive: boolean
  /** 是否已完成 */
  isCompleted: boolean
  /** 节点 X 坐标 */
  x: number
  /** 节点 Y 坐标 */
  y: number
}>()

/** 智能体类型对应 emoji 图标 */
const agentIconMap: Record<AgentType, string> = {
  [AgentType.DATA_FETCHER]: '🔍',
  [AgentType.TECHNICAL_ANALYST]: '📊',
  [AgentType.FUNDAMENTAL_ANALYST]: '📈',
  [AgentType.SENTIMENT_ANALYST]: '💭',
  [AgentType.NEWS_ANALYST]: '📰',
  [AgentType.CAPITAL_FLOW_ANALYST]: '💵',
  [AgentType.BULL_RESEARCHER]: '🐂',
  [AgentType.BEAR_RESEARCHER]: '🐻',
  [AgentType.RISK_MANAGER]: '🛡️',
  [AgentType.TRADER]: '💰',
}

/** 状态图标：pending=⏳, active=🔄, completed=✅ */
const statusIcon = computed<string>(() => {
  if (props.isCompleted) return '✅'
  if (props.isActive) return '🔄'
  return '⏳'
})
</script>

<style scoped>
.node-bg {
  fill: #1e293b;
  transition: fill 0.4s ease;
}

.is-pending .node-bg {
  fill: #1e293b;
}

.is-active .node-bg {
  fill: #1e3a5f;
}

.is-completed .node-bg {
  fill: #14532d;
}

.node-ring {
  fill: none;
  stroke: #475569;
  stroke-width: 2;
  transition: stroke 0.4s ease, stroke-width 0.4s ease;
}

.is-pending .node-ring {
  stroke: #475569;
}

.is-active .node-ring {
  stroke: #3b82f6;
  stroke-width: 2.5;
  filter: drop-shadow(0 0 4px rgba(59, 130, 246, 0.4));
}

.is-completed .node-ring {
  stroke: #22c55e;
}

.node-pulse {
  fill: none;
  stroke: #3b82f6;
  stroke-width: 2;
  animation: pulse-ring 2s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    r: 32;
    opacity: 0.6;
    stroke-width: 2;
  }
  100% {
    r: 44;
    opacity: 0;
    stroke-width: 0.5;
  }
}

.node-icon {
  font-size: 20px;
  pointer-events: none;
  user-select: none;
}

.node-name {
  font-size: 12px;
  fill: #94a3b8;
  font-weight: 600;
  pointer-events: none;
  user-select: none;
}

.is-active .node-name {
  fill: #e2e8f0;
}

.is-completed .node-name {
  fill: #86efac;
}

.agent-icon-item {
  font-size: 14px;
  pointer-events: none;
  user-select: none;
}
</style>
