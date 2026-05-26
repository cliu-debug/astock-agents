<template>
  <div class="kline-chart" ref="chartContainer"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册ECharts组件
echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
])

interface KLineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const props = defineProps<{
  data: KLineData[]
  stockCode?: string
  stockName?: string
}>()

const chartContainer = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

function initChart() {
  if (!chartContainer.value) return
  chartInstance = echarts.init(chartContainer.value, 'dark', { renderer: 'canvas' })
  updateChart()
}

function updateChart() {
  if (!chartInstance || !props.data || props.data.length === 0) return

  const dates = props.data.map(d => d.date)
  const ohlc = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map(d => d.volume)
  const ma5 = calculateMA(5, props.data)
  const ma10 = calculateMA(10, props.data)
  const ma20 = calculateMA(20, props.data)

  chartInstance.setOption({
    backgroundColor: 'transparent',
    animation: false,
    legend: { show: true, top: 0, textStyle: { color: '#94A3B8', fontSize: 11 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      borderColor: '#475569',
      textStyle: { color: '#F8FAFC', fontSize: 12 },
    },
    grid: [
      { left: 60, right: 20, top: 40, height: '60%' },
      { left: 60, right: 20, top: '75%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#334155' } }, axisTick: { show: false }, axisLabel: { color: '#64748B', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#1E293B' } } },
      { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#334155' } }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, position: 'left', axisLine: { lineStyle: { color: '#334155' } }, axisTick: { show: false }, axisLabel: { color: '#64748B', fontSize: 10 }, splitLine: { lineStyle: { color: '#1E293B' } } },
      { scale: true, gridIndex: 1, position: 'left', axisLine: { lineStyle: { color: '#334155' } }, axisTick: { show: false }, axisLabel: { color: '#64748B', fontSize: 10 }, splitLine: { lineStyle: { color: '#1E293B' } } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 60, end: 100, height: 18, bottom: 10, borderColor: '#334155', backgroundColor: '#0F172A', fillerColor: 'rgba(59, 130, 246, 0.2)', handleStyle: { color: '#3B82F6' }, textStyle: { color: '#64748B' } },
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0, itemStyle: { color: '#EF4444', color0: '#22C55E', borderColor: '#EF4444', borderColor0: '#22C55E' } },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { width: 1, color: '#F59E0B' }, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { width: 1, color: '#3B82F6' }, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { width: 1, color: '#8B5CF6' }, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0 },
      { name: '成交量', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: (params: any) => { const idx = params.dataIndex; if (!props.data[idx]) return '#64748B'; return props.data[idx].close >= props.data[idx].open ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)' } } },
    ],
  })
}

function calculateMA(days: number, data: KLineData[]): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < days - 1) { result.push(null) }
    else { let sum = 0; for (let j = 0; j < days; j++) { sum += data[i - j].close } result.push(Number((sum / days).toFixed(2))) }
  }
  return result
}

onMounted(() => { initChart(); window.addEventListener('resize', () => chartInstance?.resize()) })
onUnmounted(() => { chartInstance?.dispose() })
watch(() => props.data, () => { updateChart() }, { deep: true })
</script>

<style scoped>
.kline-chart { width: 100%; height: 400px; background: var(--color-bg-card); border-radius: var(--radius); overflow: hidden; }
</style>
