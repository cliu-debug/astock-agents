<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getReviewReport, getReviewRecords } from '@/services/api'

interface ReviewReportData {
  period: string
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  total_pnl: number
  avg_pnl_per_trade: number
  avg_holding_days: number
  max_single_gain_pct: number | null
  max_single_loss_pct: number | null
  profit_factor: number | null
  best_stock: string | null
  worst_stock: string | null
  common_mistakes: string[]
  improvement_suggestions: string[]
}

interface TradeRecordItem {
  record_id: string
  stock_code: string
  stock_name: string
  buy_price: number | null
  buy_quantity: number | null
  buy_time: string | null
  sell_price: number | null
  sell_quantity: number | null
  sell_time: string | null
  holding_days: number | null
  realized_pnl: number | null
  realized_pnl_pct: number | null
  status: string
}

const report = ref<ReviewReportData | null>(null)
const records = ref<TradeRecordItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const activeTab = ref<'report' | 'records'>('report')

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const [reportRes, recordsRes] = await Promise.all([
      getReviewReport(),
      getReviewRecords(),
    ])
    report.value = reportRes as unknown as ReviewReportData
    records.value = (recordsRes.records || []) as unknown as TradeRecordItem[]
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function formatPnl(value: number | null): string {
  if (value === null || value === undefined) return '--'
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}${value.toFixed(2)}`
}

function pnlClass(value: number | null): string {
  if (value === null || value === undefined) return ''
  return value >= 0 ? 'positive' : 'negative'
}

onMounted(loadData)
</script>

<template>
  <div class="review-view">
    <h2 class="page-title">交易复盘</h2>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- 选项卡 -->
    <div class="tab-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'report' }"
        @click="activeTab = 'report'"
      >复盘报告</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'records' }"
        @click="activeTab = 'records'"
      >交易记录</button>
    </div>

    <!-- 复盘报告 -->
    <div v-if="activeTab === 'report' && report" class="report-section">
      <!-- 核心指标 -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">胜率</div>
          <div class="metric-value" :class="report.win_rate >= 50 ? 'positive' : 'negative'">
            {{ report.win_rate }}%
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">盈亏比</div>
          <div class="metric-value" :class="(report.profit_factor ?? 0) >= 1.5 ? 'positive' : 'negative'">
            {{ report.profit_factor ?? '--' }}
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">平均盈亏</div>
          <div class="metric-value" :class="pnlClass(report.avg_pnl_per_trade)">
            {{ formatPnl(report.avg_pnl_per_trade) }}
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">总交易笔数</div>
          <div class="metric-value">{{ report.total_trades }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">盈利笔数</div>
          <div class="metric-value positive">{{ report.win_trades }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">亏损笔数</div>
          <div class="metric-value negative">{{ report.loss_trades }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">总盈亏</div>
          <div class="metric-value" :class="pnlClass(report.total_pnl)">
            {{ formatPnl(report.total_pnl) }}
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">平均持仓天数</div>
          <div class="metric-value">{{ report.avg_holding_days }}</div>
        </div>
      </div>

      <!-- 最佳/最差标的 -->
      <div class="dual-card">
        <div class="half-card">
          <div class="half-label">最佳标的</div>
          <div class="half-value positive">{{ report.best_stock || '--' }}</div>
        </div>
        <div class="half-card">
          <div class="half-label">最差标的</div>
          <div class="half-value negative">{{ report.worst_stock || '--' }}</div>
        </div>
      </div>

      <!-- 常见错误 -->
      <div v-if="report.common_mistakes?.length" class="section-card">
        <h3 class="section-title">常见错误</h3>
        <ul class="mistake-list">
          <li v-for="(mistake, idx) in report.common_mistakes" :key="idx" class="mistake-item">
            <span class="mistake-marker">!</span>
            <span>{{ mistake }}</span>
          </li>
        </ul>
      </div>

      <!-- 改进建议 -->
      <div v-if="report.improvement_suggestions?.length" class="section-card">
        <h3 class="section-title">改进建议</h3>
        <ul class="suggestion-list">
          <li v-for="(suggestion, idx) in report.improvement_suggestions" :key="idx" class="suggestion-item">
            <span class="suggestion-marker">&gt;</span>
            <span>{{ suggestion }}</span>
          </li>
        </ul>
      </div>
    </div>

    <!-- 交易记录列表 -->
    <div v-if="activeTab === 'records'" class="records-section">
      <div v-if="records.length" class="table-wrapper card">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>股票</th>
              <th>方向</th>
              <th>买入价</th>
              <th>卖出价</th>
              <th>数量</th>
              <th>盈亏</th>
              <th>盈亏%</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rec in records" :key="rec.record_id">
              <td>{{ (rec.buy_time || '').substring(0, 10) }}</td>
              <td>{{ rec.stock_name || rec.stock_code }}</td>
              <td>{{ rec.status === '已平仓' ? '买卖' : '买入' }}</td>
              <td>{{ rec.buy_price?.toFixed(2) ?? '--' }}</td>
              <td>{{ rec.sell_price?.toFixed(2) ?? '--' }}</td>
              <td>{{ rec.buy_quantity ?? '--' }}</td>
              <td :class="pnlClass(rec.realized_pnl)">{{ formatPnl(rec.realized_pnl) }}</td>
              <td :class="pnlClass(rec.realized_pnl_pct)">{{ rec.realized_pnl_pct !== null && rec.realized_pnl_pct !== undefined ? formatPnl(rec.realized_pnl_pct) + '%' : '--' }}</td>
              <td>
                <span class="status-tag" :class="rec.status === '已平仓' ? 'status-closed' : 'status-holding'">
                  {{ rec.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无交易记录</div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>
  </div>
</template>

<style scoped>
.review-view {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 20px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 4px;
  width: fit-content;
}

.tab-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn.active {
  background: var(--color-accent);
  color: #fff;
}

.tab-btn:hover:not(.active) {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.metric-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

.dual-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.half-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 14px 16px;
}

.half-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.half-value {
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
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

.mistake-list,
.suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.mistake-item,
.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
}

.mistake-item:last-child,
.suggestion-item:last-child {
  border-bottom: none;
}

.mistake-marker {
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

.suggestion-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(37, 99, 235, 0.15);
  color: var(--color-accent);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}

.status-closed {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.status-holding {
  background: rgba(234, 179, 8, 0.12);
  color: #eab308;
}

.positive { color: #22c55e; }
.negative { color: #ef4444; }

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--color-text-muted);
  font-size: 14px;
}

.loading-state {
  text-align: center;
  padding: 40px;
  color: var(--color-text-muted);
}

.error-msg {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius);
  padding: 12px 16px;
  color: #ef4444;
  font-size: 13px;
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .dual-card { grid-template-columns: 1fr; }
}
</style>
