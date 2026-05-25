<template>
  <div class="agent-output" v-if="output">
    <!-- 摘要 -->
    <div class="output-section">
      <div class="section-label">摘要</div>
      <div class="output-summary">{{ output.summary }}</div>
    </div>

    <!-- 关键指标标签 -->
    <div class="output-section" v-if="hasKeyMetrics">
      <div class="section-label">关键指标</div>
      <div class="metrics-list">
        <span
          v-for="(value, key) in output.keyMetrics"
          :key="key"
          class="metric-tag"
        >
          <span class="metric-key">{{ key }}</span>
          <span class="metric-value">{{ value }}</span>
        </span>
      </div>
    </div>

    <!-- 交易信号 -->
    <div class="output-section" v-if="output.signal">
      <div class="section-label">信号</div>
      <div class="signal-badge" :class="`signal-${output.signal}`" :style="{ borderColor: signalColor, color: signalColor }">
        <span class="signal-icon">{{ signalIcon }}</span>
        <span class="signal-text">{{ signalText }}</span>
      </div>
    </div>

    <!-- 置信度 -->
    <div class="output-section" v-if="output.confidence !== undefined">
      <div class="section-label">置信度</div>
      <div class="confidence-bar">
        <div class="confidence-fill" :style="{ width: `${output.confidence}%`, background: confidenceColor }"></div>
        <span class="confidence-text">{{ output.confidence }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Signal } from '@/types/agent'
import type { AgentOutput } from '@/types/agent'

const props = defineProps<{
  output: AgentOutput
}>()

/** 是否有关键指标 */
const hasKeyMetrics = computed((): boolean => {
  return !!props.output.keyMetrics && Object.keys(props.output.keyMetrics).length > 0
})

/** 信号对应颜色 */
const signalColor = computed((): string => {
  const colorMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '#22C55E',
    [Signal.BUY]: '#4ADE80',
    [Signal.HOLD]: '#F59E0B',
    [Signal.SELL]: '#F87171',
    [Signal.STRONG_SELL]: '#EF4444',
  }
  return props.output.signal ? colorMap[props.output.signal] || '#94A3B8' : '#94A3B8'
})

/** 信号对应图标 */
const signalIcon = computed((): string => {
  const iconMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '🚀',
    [Signal.BUY]: '📈',
    [Signal.HOLD]: '⏸️',
    [Signal.SELL]: '📉',
    [Signal.STRONG_SELL]: '🔻',
  }
  return props.output.signal ? iconMap[props.output.signal] || '📊' : '📊'
})

/** 信号对应中文文本 */
const signalText = computed((): string => {
  const textMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '强烈买入',
    [Signal.BUY]: '买入',
    [Signal.HOLD]: '持有',
    [Signal.SELL]: '卖出',
    [Signal.STRONG_SELL]: '强烈卖出',
  }
  return props.output.signal ? textMap[props.output.signal] || props.output.signal : ''
})

/** 置信度对应颜色 */
const confidenceColor = computed((): string => {
  const confidence = props.output.confidence ?? 0
  if (confidence >= 80) return '#22C55E'
  if (confidence >= 60) return '#F59E0B'
  return '#EF4444'
})
</script>

<style scoped>
.agent-output {
  background: #1E293B;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.output-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 11px;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.output-summary {
  font-size: 13px;
  color: #CBD5E1;
  line-height: 1.6;
}

/* 关键指标 */
.metrics-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.metric-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  font-size: 12px;
}

.metric-key {
  color: #94A3B8;
}

.metric-value {
  color: #F8FAFC;
  font-weight: 600;
}

/* 交易信号 */
.signal-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid;
  background: rgba(255, 255, 255, 0.04);
  font-weight: 600;
  font-size: 13px;
}

.signal-icon {
  font-size: 14px;
}

.signal-text {
  white-space: nowrap;
}

/* 置信度 */
.confidence-bar {
  position: relative;
  height: 24px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 12px;
  transition: width 0.6s ease;
  min-width: 0;
}

.confidence-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 600;
  color: #F8FAFC;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}
</style>
