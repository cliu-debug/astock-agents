<template>
  <div class="workflow-graph">
    <svg
      :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
      class="graph-svg"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <filter id="glow-blue" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="glow-green" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <WorkflowEdge
        v-for="edge in edges"
        :key="edge.id"
        :x1="edge.x1"
        :y1="edge.y1"
        :x2="edge.x2"
        :y2="edge.y2"
        :active="edge.active"
        :animated="edge.animated"
      />

      <WorkflowNode
        v-for="node in nodeData"
        :key="node.phase.stage"
        :phase="node.phase"
        :is-active="node.isActive"
        :is-completed="node.isCompleted"
        :x="node.x"
        :y="node.y"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WorkflowStage } from '@/types/agent'
import type { Agent, WorkflowPhase } from '@/types/agent'
import WorkflowNode from './WorkflowNode.vue'
import WorkflowEdge from './WorkflowEdge.vue'

const props = defineProps<{
  /** 智能体列表 */
  agents: Agent[]
  /** 当前工作流阶段 */
  currentPhase: WorkflowStage
}>()

/** SVG 画布尺寸 */
const svgWidth = 900
const svgHeight = 220

/** 阶段排列顺序 */
const stageOrder: WorkflowStage[] = [
  WorkflowStage.DATA_FETCH,
  WorkflowStage.PARALLEL_ANALYSIS,
  WorkflowStage.DEBATE,
  WorkflowStage.RISK_ASSESSMENT,
  WorkflowStage.DECISION,
]

/** 阶段名称映射 */
const stageNameMap: Record<WorkflowStage, string> = {
  [WorkflowStage.DATA_FETCH]: '数据获取',
  [WorkflowStage.PARALLEL_ANALYSIS]: '并行分析',
  [WorkflowStage.DEBATE]: '多空辩论',
  [WorkflowStage.RISK_ASSESSMENT]: '风险评估',
  [WorkflowStage.DECISION]: '最终决策',
}

/** 阶段包含的智能体类型 */
const stageAgentMap: Record<WorkflowStage, string[]> = {
  [WorkflowStage.DATA_FETCH]: ['data_fetcher'],
  [WorkflowStage.PARALLEL_ANALYSIS]: ['technical', 'fundamental', 'sentiment', 'news', 'capital_flow'],
  [WorkflowStage.DEBATE]: ['bull', 'bear'],
  [WorkflowStage.RISK_ASSESSMENT]: ['risk'],
  [WorkflowStage.DECISION]: ['trader'],
}

/**
 * 判断阶段是否已完成
 * @param stage - 工作流阶段
 * @returns 是否已完成
 */
function isStageCompleted(stage: WorkflowStage): boolean {
  const stageIdx = stageOrder.indexOf(stage)
  const currentIdx = stageOrder.indexOf(props.currentPhase)
  return stageIdx < currentIdx
}

/**
 * 判断阶段是否为当前激活阶段
 * @param stage - 工作流阶段
 * @returns 是否激活
 */
function isStageActive(stage: WorkflowStage): boolean {
  return stage === props.currentPhase
}

/** 计算节点数据 */
const nodeData = computed(() => {
  const nodeSpacing = svgWidth / (stageOrder.length + 1)
  return stageOrder.map((stage, index) => {
    const phase: WorkflowPhase = {
      stage,
      name: stageNameMap[stage],
      agents: stageAgentMap[stage] as unknown as WorkflowPhase['agents'],
      status: isStageActive(stage) ? 'active' : isStageCompleted(stage) ? 'completed' : 'pending',
    }
    return {
      phase,
      isActive: isStageActive(stage),
      isCompleted: isStageCompleted(stage),
      x: nodeSpacing * (index + 1),
      y: 80,
    }
  })
})

/** 连线数据 */
const edges = computed(() => {
  const result: {
    id: string
    x1: number
    y1: number
    x2: number
    y2: number
    active: boolean
    animated: boolean
  }[] = []

  for (let i = 0; i < nodeData.value.length - 1; i++) {
    const from = nodeData.value[i]
    const to = nodeData.value[i + 1]
    result.push({
      id: `edge-${i}`,
      x1: from.x + 32,
      y1: from.y,
      x2: to.x - 32,
      y2: to.y,
      active: from.isActive || from.isCompleted,
      animated: from.isActive,
    })
  }

  return result
})
</script>

<style scoped>
.workflow-graph {
  width: 100%;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  border-radius: 16px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.graph-svg {
  width: 100%;
  height: auto;
  display: block;
}
</style>
