<script setup lang="ts">
import { ref } from 'vue'
import { macroAnalyze, type MacroAnalysisRequest } from '@/services/api'

interface MacroData {
  cycle_phase?: string
  cycle_description?: string
  industry_fit?: Record<string, string>
  policy_assessment?: string
  policy_details?: string[]
  risk_level?: string
  risk_factors?: string[]
  signal?: string
  confidence?: number
  summary?: string
}

const stockCode = ref('')
const stockName = ref('')
const industry = ref('')
const result = ref<MacroData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function handleAnalyze() {
  if (!stockCode.value.trim()) {
    error.value = '请输入股票代码'
    return
  }
  loading.value = true
  error.value = null
  result.value = null
  try {
    const params: MacroAnalysisRequest = {
      stock_code: stockCode.value.trim(),
      stock_name: stockName.value.trim() || undefined,
      industry: industry.value.trim() || undefined,
    }
    const res = await macroAnalyze(params) as { success: boolean; data: MacroData }
    result.value = res.data
  } catch (e) {
    error.value = e instanceof Error ? e.message : '分析失败'
  } finally {
    loading.value = false
  }
}

function riskLevelClass(level: string | undefined): string {
  if (!level) return ''
  const lower = level.toLowerCase()
  if (lower.includes('高') || lower.includes('high')) return 'risk-high'
  if (lower.includes('中') || lower.includes('medium')) return 'risk-medium'
  return 'risk-low'
}

function signalClass(signal: string | undefined): string {
  if (!signal) return ''
  const lower = signal.toLowerCase()
  if (lower.includes('买入') || lower.includes('buy')) return 'positive'
  if (lower.includes('卖出') || lower.includes('sell')) return 'negative'
  return ''
}
</script>

<template>
  <div class="macro-view">
    <h2 class="page-title">宏观分析</h2>

    <!-- 输入面板 -->
    <div class="input-panel card">
      <div class="form-grid">
        <div class="form-field">
          <label class="field-label">股票代码</label>
          <input v-model="stockCode" placeholder="600519.SH" class="input" @keyup.enter="handleAnalyze" />
        </div>
        <div class="form-field">
          <label class="field-label">股票名称</label>
          <input v-model="stockName" placeholder="贵州茅台" class="input" />
        </div>
        <div class="form-field">
          <label class="field-label">所属行业</label>
          <input v-model="industry" placeholder="白酒" class="input" @keyup.enter="handleAnalyze" />
        </div>
        <div class="form-field form-action">
          <button class="btn-primary" :disabled="loading" @click="handleAnalyze">
            {{ loading ? '分析中...' : '开始分析' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- 分析结果 -->
    <div v-if="result" class="result-section">
      <!-- 信号与置信度 -->
      <div class="signal-bar">
        <div class="signal-item">
          <span class="signal-label">宏观信号</span>
          <span class="signal-value" :class="signalClass(result.signal)">{{ result.signal || '--' }}</span>
        </div>
        <div class="signal-item">
          <span class="signal-label">置信度</span>
          <span class="signal-value">{{ result.confidence ?? '--' }}{{ result.confidence ? '%' : '' }}</span>
        </div>
        <div class="signal-item">
          <span class="signal-label">风险等级</span>
          <span class="signal-value" :class="riskLevelClass(result.risk_level)">{{ result.risk_level || '--' }}</span>
        </div>
      </div>

      <!-- 美林时钟周期定位 -->
      <div v-if="result.cycle_phase" class="section-card">
        <h3 class="section-title">美林时钟经济周期定位</h3>
        <div class="cycle-phase">{{ result.cycle_phase }}</div>
        <p v-if="result.cycle_description" class="cycle-desc">{{ result.cycle_description }}</p>
      </div>

      <!-- 行业适配度 -->
      <div v-if="result.industry_fit && Object.keys(result.industry_fit).length" class="section-card">
        <h3 class="section-title">行业适配度分析</h3>
        <div class="industry-grid">
          <div v-for="(fit, name) in result.industry_fit" :key="name" class="industry-item">
            <div class="industry-name">{{ name }}</div>
            <div class="industry-fit" :class="fit.includes('高') || fit.includes('适配') ? 'positive' : fit.includes('低') || fit.includes('回避') ? 'negative' : ''">
              {{ fit }}
            </div>
          </div>
        </div>
      </div>

      <!-- 政策环境 -->
      <div v-if="result.policy_assessment" class="section-card">
        <h3 class="section-title">政策环境评估</h3>
        <p class="policy-text">{{ result.policy_assessment }}</p>
        <ul v-if="result.policy_details?.length" class="policy-list">
          <li v-for="(detail, idx) in result.policy_details" :key="idx">{{ detail }}</li>
        </ul>
      </div>

      <!-- 风险因素 -->
      <div v-if="result.risk_factors?.length" class="section-card">
        <h3 class="section-title">风险因素</h3>
        <ul class="risk-list">
          <li v-for="(factor, idx) in result.risk_factors" :key="idx" class="risk-item">
            <span class="risk-marker">!</span>
            <span>{{ factor }}</span>
          </li>
        </ul>
      </div>

      <!-- 综合摘要 -->
      <div v-if="result.summary" class="section-card">
        <h3 class="section-title">综合摘要</h3>
        <p class="summary-text">{{ result.summary }}</p>
      </div>
    </div>

    <div v-if="loading" class="loading-state">宏观分析中，请稍候...</div>
  </div>
</template>

<style scoped>
.macro-view {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 20px;
}

.input-panel {
  margin-bottom: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  align-items: end;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.form-action {
  display: flex;
  align-items: flex-end;
}

.signal-bar {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.signal-item {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.signal-label {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.signal-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.section-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.cycle-phase {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-accent);
  margin-bottom: 8px;
}

.cycle-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.industry-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.industry-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.industry-name {
  font-size: 13px;
  color: var(--color-text-primary);
  font-weight: 500;
}

.industry-fit {
  font-size: 12px;
  font-weight: 600;
}

.policy-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 10px;
}

.policy-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.policy-list li {
  padding: 6px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  padding-left: 14px;
  position: relative;
}

.policy-list li::before {
  content: '-';
  position: absolute;
  left: 0;
  color: var(--color-accent);
}

.policy-list li:last-child {
  border-bottom: none;
}

.risk-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.risk-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
}

.risk-item:last-child {
  border-bottom: none;
}

.risk-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.summary-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.positive { color: #22c55e; }
.negative { color: #ef4444; }

.risk-high { color: #ef4444; }
.risk-medium { color: #eab308; }
.risk-low { color: #22c55e; }

.error-msg {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius);
  padding: 12px 16px;
  color: #ef4444;
  font-size: 13px;
  margin-bottom: 16px;
}

.loading-state {
  text-align: center;
  padding: 40px;
  color: var(--color-text-muted);
}

@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr 1fr; }
  .signal-bar { grid-template-columns: 1fr; }
  .industry-grid { grid-template-columns: 1fr; }
}
</style>
