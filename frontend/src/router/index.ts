import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'analysis',
      component: () => import('@/views/AnalysisView.vue'),
      meta: { title: '智能体分析' },
    },
    {
      path: '/market',
      name: 'market',
      component: () => import('@/views/MarketView.vue'),
      meta: { title: '市场总览' },
    },
    {
      path: '/screener',
      name: 'screener',
      component: () => import('@/views/ScreenerView.vue'),
      meta: { title: '选股' },
    },
    {
      path: '/watchlist',
      name: 'watchlist',
      component: () => import('@/views/WatchlistView.vue'),
      meta: { title: '自选股' },
    },
    {
      path: '/trading',
      name: 'trading',
      component: () => import('@/views/TradingView.vue'),
      meta: { title: '模拟交易' },
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('@/views/BacktestView.vue'),
      meta: { title: '策略回测' },
    },
    {
      path: '/tracker',
      name: 'tracker',
      component: () => import('@/views/TrackerView.vue'),
      meta: { title: '追踪中心' },
    },
    {
      path: '/review',
      name: 'review',
      component: () => import('@/views/ReviewView.vue'),
      meta: { title: '复盘' },
    },
    {
      path: '/macro',
      name: 'macro',
      component: () => import('@/views/MacroView.vue'),
      meta: { title: '宏观分析' },
    },
    {
      path: '/decision',
      name: 'decision',
      component: () => import('@/views/DecisionView.vue'),
      meta: { title: '决策中心' },
    },
    {
      path: '/capital-flow',
      name: 'capitalFlow',
      component: () => import('@/views/CapitalFlowView.vue'),
      meta: { title: '资金流向' },
    },

    {
      path: '/position-sizing',
      name: 'positionSizing',
      component: () => import('@/views/PositionSizingView.vue'),
      meta: { title: '仓位计算' },
    },
    {
      path: '/scheduler',
      name: 'scheduler',
      component: () => import('@/views/SchedulerView.vue'),
      meta: { title: '调度器' },
    },
    {
      path: '/notification',
      name: 'notification',
      component: () => import('@/views/NotificationView.vue'),
      meta: { title: '通知中心' },
    },
  ],
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'AStockAgents'} - AStockAgents`
})

export default router
