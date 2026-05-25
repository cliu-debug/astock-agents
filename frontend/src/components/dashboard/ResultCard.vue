<template>
  <div class="result-card" v-if="result">
    <!-- 渐变背景装饰 -->
    <div class="gradient-bg" :class="`gradient-${signalDirection}`"></div>

    <div class="result-content">
      <!-- 股票信息 -->
      <div class="stock-info">
        <div class="stock-code">{{ result.stockCode }}</div>
        <div class="stock-name">{{ result.stockName }}</div>
        <div class="stock-price">
          <span class="price-value">¥{{ result.currentPrice.toFixed(2) }}</span>
          <span class="price-change" :class="result.changePercent >= 0 ? 'up' : 'down'">
            {{ result.changePercent >= 0 ? '+' : '' }}{{ result.changePercent.toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- 交易信号 -->
      <div class="signal-section">
        <div class="signal-badge" :class="`signal-${result.signal}`" :style="{ borderColor: signalColor, color: signalColor }">
          <span class="signal-icon">{{ signalIcon }}</span>
          <span class="signal-text">{{ signalText }}</span>
        </div>
      </div>

      <!-- 评分与置信度 -->
      <div class="scores-section">
        <div class="score-item">
          <div class="score-label">综合评分</div>
          <div class="score-value" :style="{ color: scoreColor }">{{ result.score }}</div>
          <div class="score-bar">
            <div class="score-fill" :style="{ width: `${result.score}%`, background: scoreColor }"></div>
          </div>
        </div>
        <div class="score-item">
          <div class="score-label">置信度</div>
          <div class="score-value" :style="{ color: confidenceColor }">{{ result.confidence }}%</div>
          <div class="score-bar">
            <div class="score-fill" :style="{ width: `${result.confidence}%`, background: confidenceColor }"></div>
          </div>
        </div>
      </div>

      <!-- 风险等级 -->
      <div class="risk-section">
        <div class="risk-label">风险等级</div>
        <div class="risk-badge" :class="`risk-${result.riskLevel}`" :style="{ borderColor: riskColor, color: riskColor }">
          {{ riskText }}
        </div>
      </div>

      <!-- 摘要 -->
      <div class="summary-section">
        <div class="summary-label">分析摘要</div>
        <div class="summary-text">{{ result.summary }}</div>
      </div>

      <!-- 各智能体观点 -->
      <div class="views-section" v-if="result.agentViews.length > 0">
        <div class="views-label">智能体观点</div>
        <div class="views-list">
          <div
            v-for="(view, index) in result.agentViews"
            :key="index"
            class="view-item"
          >
            <div class="view-summary">{{ view.summary }}</div>
            <div class="view-meta" v-if="view.signal || view.confidence !== undefined">
              <span v-if="view.signal" class="view-signal" :style="{ color: getViewSignalColor(view.signal) }">
                {{ getViewSignalText(view.signal) }}
              </span>
              <span v-if="view.confidence !== undefined" class="view-confidence">
                置信度: {{ view.confidence }}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 无数据占位 -->
  <div class="result-card result-empty" v-else>
    <div class="empty-icon">📊</div>
    <div class="empty-text">等待分析完成...</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Signal, RiskLevel } from '@/types/agent'
import type { FinalResult } from '@/types/agent'

const props = defineProps<{
  result: FinalResult | null
}>()

/** 信号方向（用于渐变背景） */
const signalDirection = computed((): string => {
  if (!props.result) return 'neutral'
  const bullishSignals: Signal[] = [Signal.STRONG_BUY, Signal.BUY]
  const bearishSignals: Signal[] = [Signal.SELL, Signal.STRONG_SELL]
  if (bullishSignals.includes(props.result.signal)) return 'bullish'
  if (bearishSignals.includes(props.result.signal)) return 'bearish'
  return 'neutral'
})

/** 信号颜色 */
const signalColor = computed((): string => {
  if (!props.result) return '#94A3B8'
  const colorMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '#22C55E',
    [Signal.BUY]: '#4ADE80',
    [Signal.HOLD]: '#F59E0B',
    [Signal.SELL]: '#F87171',
    [Signal.STRONG_SELL]: '#EF4444',
  }
  return colorMap[props.result.signal] || '#94A3B8'
})

/** 信号图标 */
const signalIcon = computed((): string => {
  if (!props.result) return '📊'
  const iconMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '🚀',
    [Signal.BUY]: '📈',
    [Signal.HOLD]: '⏸️',
    [Signal.SELL]: '📉',
    [Signal.STRONG_SELL]: '🔻',
  }
  return iconMap[props.result.signal] || '📊'
})

/** 信号中文文本 */
const signalText = computed((): string => {
  if (!props.result) return ''
  const textMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '强烈买入',
    [Signal.BUY]: '买入',
    [Signal.HOLD]: '持有',
    [Signal.SELL]: '卖出',
    [Signal.STRONG_SELL]: '强烈卖出',
  }
  return textMap[props.result.signal] || ''
})

/** 评分颜色 */
const scoreColor = computed((): string => {
  if (!props.result) return '#94A3B8'
  if (props.result.score >= 80) return '#22C55E'
  if (props.result.score >= 60) return '#F59E0B'
  if (props.result.score >= 40) return '#F97316'
  return '#EF4444'
})

/** 置信度颜色 */
const confidenceColor = computed((): string => {
  if (!props.result) return '#94A3B8'
  if (props.result.confidence >= 80) return '#22C55E'
  if (props.result.confidence >= 60) return '#F59E0B'
  return '#EF4444'
})

/** 风险颜色 */
const riskColor = computed((): string => {
  if (!props.result) return '#94A3B8'
  const colorMap: Record<RiskLevel, string> = {
    [RiskLevel.LOW]: '#22C55E',
    [RiskLevel.MEDIUM]: '#F59E0B',
    [RiskLevel.HIGH]: '#F97316',
    [RiskLevel.EXTREME]: '#EF4444',
  }
  return colorMap[props.result.riskLevel] || '#94A3B8'
})

/** 风险中文文本 */
const riskText = computed((): string => {
  if (!props.result) return ''
  const textMap: Record<RiskLevel, string> = {
    [RiskLevel.LOW]: '低风险',
    [RiskLevel.MEDIUM]: '中等风险',
    [RiskLevel.HIGH]: '高风险',
    [RiskLevel.EXTREME]: '极高风险',
  }
  return textMap[props.result.riskLevel] || ''
})

/** 获取智能体观点信号颜色 */
const getViewSignalColor = (signal: Signal): string => {
  const colorMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '#22C55E',
    [Signal.BUY]: '#4ADE80',
    [Signal.HOLD]: '#F59E0B',
    [Signal.SELL]: '#F87171',
    [Signal.STRONG_SELL]: '#EF4444',
  }
  return colorMap[signal] || '#94A3B8'
}

/** 获取智能体观点信号中文文本 */
const getViewSignalText = (signal: Signal): string => {
  const textMap: Record<Signal, string> = {
    [Signal.STRONG_BUY]: '强烈买入',
    [Signal.BUY]: '买入',
    [Signal.HOLD]: '持有',
    [Signal.SELL]: '卖出',
    [Signal.STRONG_SELL]: '强烈卖出',
  }
  return textMap[signal] || signal
}
</script>

<style scoped>
.result-card {
  position: relative;
  background: #1E293B;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

/* 渐变背景 */
.gradient-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 120px;
  opacity: 0.15;
  pointer-events: none;
}

.gradient-bullish {
  background: linear-gradient(135deg, #22C55E 0%, #10B981 50%, #059669 100%);
}

.gradient-bearish {
  background: linear-gradient(135deg, #EF4444 0%, #DC2626 50%, #B91C1C 100%);
}

.gradient-neutral {
  background: linear-gradient(135deg, #F59E0B 0%, #D97706 50%, #B45309 100%);
}

.result-content {
  position: relative;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 股票信息 */
.stock-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stock-code {
  font-size: 12px;
  color: #94A3B8;
  font-weight: 500;
}

.stock-name {
  font-size: 20px;
  font-weight: 700;
  color: #F8FAFC;
}

.stock-price {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 4px;
}

.price-value {
  font-size: 24px;
  font-weight: 700;
  color: #F8FAFC;
}

.price-change {
  font-size: 14px;
  font-weight: 600;
}

.price-change.up {
  color: #EF4444;
}

.price-change.down {
  color: #22C55E;
}

/* 交易信号 */
.signal-section {
  display: flex;
  align-items: center;
}

.signal-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 24px;
  border: 2px solid;
  background: rgba(255, 255, 255, 0.04);
  font-weight: 700;
  font-size: 16px;
}

.signal-icon {
  font-size: 18px;
}

.signal-text {
  white-space: nowrap;
}

/* 评分与置信度 */
.scores-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.score-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.score-label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}

.score-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.score-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}

/* 风险等级 */
.risk-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.risk-label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}

.risk-badge {
  padding: 4px 14px;
  border-radius: 16px;
  border: 1px solid;
  background: rgba(255, 255, 255, 0.04);
  font-size: 13px;
  font-weight: 600;
}

/* 摘要 */
.summary-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}

.summary-text {
  font-size: 14px;
  color: #CBD5E1;
  line-height: 1.7;
}

/* 智能体观点 */
.views-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.views-label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}

.views-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.view-item {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  border-left: 3px solid rgba(255, 255, 255, 0.1);
}

.view-summary {
  font-size: 13px;
  color: #CBD5E1;
  line-height: 1.5;
  margin-bottom: 4px;
}

.view-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.view-signal {
  font-weight: 600;
}

.view-confidence {
  color: #94A3B8;
}

/* 空状态 */
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  gap: 12px;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  color: #64748B;
}
</style>
