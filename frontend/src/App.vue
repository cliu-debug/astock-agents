<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const sidebarCollapsed = ref(false)

/** 导航项配置 - SVG 图标 + 文字 */
const navItems = [
  {
    path: '/',
    name: 'analysis',
    label: '智能体分析',
    icon: 'analysis',
  },
  {
    path: '/market',
    name: 'market',
    label: '市场总览',
    icon: 'market',
  },
  {
    path: '/screener',
    name: 'screener',
    label: '选股',
    icon: 'screener',
  },
  {
    path: '/watchlist',
    name: 'watchlist',
    label: '自选股',
    icon: 'watchlist',
  },
  {
    path: '/trading',
    name: 'trading',
    label: '模拟交易',
    icon: 'trading',
  },
  {
    path: '/backtest',
    name: 'backtest',
    label: '策略回测',
    icon: 'backtest',
  },
  {
    path: '/tracker',
    name: 'tracker',
    label: '追踪中心',
    icon: 'tracker',
  },
  {
    path: '/review',
    name: 'review',
    label: '复盘',
    icon: 'review',
  },
  {
    path: '/macro',
    name: 'macro',
    label: '宏观',
    icon: 'macro',
  },
  {
    path: '/decision',
    name: 'decision',
    label: '决策中心',
    icon: 'decision',
  },
  {
    path: '/capital-flow',
    name: 'capitalFlow',
    label: '资金流向',
    icon: 'capital-flow',
  },

  {
    path: '/position-sizing',
    name: 'positionSizing',
    label: '仓位计算',
    icon: 'position-sizing',
  },
  {
    path: '/scheduler',
    name: 'scheduler',
    label: '调度器',
    icon: 'scheduler',
  },
  {
    path: '/notification',
    name: 'notification',
    label: '通知中心',
    icon: 'notification',
  },
]

const currentNav = computed(() => route.name as string)

function navigateTo(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="app-layout">
    <!-- 侧边导航栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="logo" v-if="!sidebarCollapsed">
          <svg class="logo-icon" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="3" width="20" height="18" rx="2" stroke="#2563EB" stroke-width="1.5"/>
            <path d="M6 15L9 10L12 13L15 8L18 12" stroke="#2563EB" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="logo-text">AStock<span class="logo-accent">Agents</span></span>
        </div>
        <svg v-else class="logo-icon-only" width="24" height="24" viewBox="0 0 24 24" fill="none">
          <rect x="2" y="3" width="20" height="18" rx="2" stroke="#2563EB" stroke-width="1.5"/>
          <path d="M6 15L9 10L12 13L15 8L18 12" stroke="#2563EB" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.name"
          class="nav-item"
          :class="{ active: currentNav === item.name }"
          @click="navigateTo(item.path)"
          :title="item.label"
        >
          <!-- 智能体分析 -->
          <svg v-if="item.icon === 'analysis'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
          <!-- 市场总览 -->
          <svg v-else-if="item.icon === 'market'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          <!-- 选股 -->
          <svg v-else-if="item.icon === 'screener'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 4h16v16H4z"/><path d="M9 9h6M9 13h4"/>
          </svg>
          <!-- 自选股 -->
          <svg v-else-if="item.icon === 'watchlist'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.27 5.82 21 7 14.14l-5-4.87 6.91-1.01L12 2z"/>
          </svg>
          <!-- 模拟交易 -->
          <svg v-else-if="item.icon === 'trading'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
          </svg>
          <!-- 策略回测 -->
          <svg v-else-if="item.icon === 'backtest'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 3v18h18"/><path d="M7 16l4-6 4 4 5-8"/>
          </svg>
          <!-- 追踪中心 -->
          <svg v-else-if="item.icon === 'tracker'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          <!-- 复盘 -->
          <svg v-else-if="item.icon === 'review'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="9"/><path d="M3 12h1M20 12h1M12 3v1M12 20v1"/>
          </svg>
          <!-- 宏观 -->
          <svg v-else-if="item.icon === 'macro'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10A15.3 15.3 0 0112 2z"/>
          </svg>
          <!-- 决策中心 -->
          <svg v-else-if="item.icon === 'decision'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/>
          </svg>
          <!-- 资金流向 -->
          <svg v-else-if="item.icon === 'capital-flow'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2v20M17 7l-5-5-5 5"/><path d="M7 17l5 5 5-5"/>
          </svg>

          <!-- 仓位计算 -->
          <svg v-else-if="item.icon === 'position-sizing'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
          </svg>
          <!-- 调度器 -->
          <svg v-else-if="item.icon === 'scheduler'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <!-- 通知中心 -->
          <svg v-else-if="item.icon === 'notification'" class="nav-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>
          </svg>
          <span class="nav-label" v-if="!sidebarCollapsed">{{ item.label }}</span>
        </button>
      </nav>

      <button class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline v-if="sidebarCollapsed" points="9 18 15 12 9 6"/>
          <polyline v-else points="15 18 9 12 15 6"/>
        </svg>
      </button>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.sidebar {
  width: 200px;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 56px;
}

.sidebar-header {
  padding: 16px 12px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 56px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}

.logo-accent {
  color: var(--color-accent);
}

.sidebar-nav {
  flex: 1;
  padding: 8px 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
  width: 100%;
  text-align: left;
}

.nav-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: rgba(37, 99, 235, 0.1);
  color: var(--color-accent);
}

.nav-svg {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

.sidebar-toggle {
  margin: 8px;
  padding: 8px;
  background: var(--color-bg-hover);
  border: none;
  border-radius: var(--radius);
  color: var(--color-text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.sidebar-toggle:hover {
  background: var(--color-border);
  color: var(--color-text-primary);
}

.main-content {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

@media (max-width: 768px) {
  .sidebar {
    width: 56px;
  }
  .sidebar .nav-label {
    display: none;
  }
  .sidebar .logo-text {
    display: none;
  }
  .sidebar-toggle {
    display: none;
  }
}
</style>
