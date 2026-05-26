<template>
  <div class="agent-scene" ref="containerRef">
    <canvas ref="canvasRef"></canvas>

    <div class="scene-hints">
      <span>拖拽旋转</span>
      <span>滚轮缩放</span>
      <span>点击智能体查看详情</span>
    </div>

    <Transition name="fade">
      <div v-if="selectedAgent" class="agent-detail-panel">
        <div class="detail-header">
          <span class="detail-icon">{{ selectedAgent.icon }}</span>
          <span class="detail-name">{{ selectedAgent.name }}</span>
          <button @click="selectedAgent = null" class="close-btn">✕</button>
        </div>
        <div class="detail-body">
          <div class="detail-status">
            <span class="label">状态:</span>
            <span class="status-badge" :class="`status-${selectedAgent.status}`">
              <span class="status-dot"></span>
              {{ statusTextMap[selectedAgent.status] || selectedAgent.status }}
            </span>
          </div>
          <div class="detail-progress">
            <span class="label">进度:</span>
            <div class="progress-ring">
              <svg viewBox="0 0 100 100">
                <circle
                  class="progress-bg"
                  cx="50" cy="50" r="45"
                  fill="none"
                  stroke="rgba(255,255,255,0.1)"
                  stroke-width="8"
                />
                <circle
                  class="progress-fill"
                  cx="50" cy="50" r="45"
                  fill="none"
                  :stroke="selectedAgent.color"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="283"
                  :stroke-dashoffset="283 - (283 * selectedAgent.progress / 100)"
                  transform="rotate(-90 50 50)"
                />
              </svg>
              <span class="progress-value">{{ selectedAgent.progress }}%</span>
            </div>
          </div>
          <div v-if="selectedAgent.currentTask" class="detail-task">
            <span class="label">当前任务:</span>
            <span class="task-text">{{ selectedAgent.currentTask }}</span>
          </div>
          <div v-if="selectedAgent.output" class="detail-output">
            <span class="label">输出摘要:</span>
            <p>{{ selectedAgent.output.summary }}</p>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { AgentStatus, AgentType } from '@/types/agent'
import type { Agent } from '@/types/agent'

const props = defineProps<{
  agents: Agent[]
}>()

const containerRef = ref<HTMLElement>()
const canvasRef = ref<HTMLCanvasElement>()
const selectedAgent = ref<Agent | null>(null)

/** 状态文字映射 */
const statusTextMap: Record<string, string> = {
  [AgentStatus.IDLE]: '空闲',
  [AgentStatus.INITIALIZING]: '初始化',
  [AgentStatus.RUNNING]: '运行中',
  [AgentStatus.WAITING]: '等待中',
  [AgentStatus.COMPLETED]: '已完成',
  [AgentStatus.FAILED]: '失败',
}

/** 智能体类型颜色映射 */
const agentColorMap: Record<AgentType, string> = {
  [AgentType.DATA_FETCHER]: '#06B6D4',
  [AgentType.TECHNICAL_ANALYST]: '#3B82F6',
  [AgentType.FUNDAMENTAL_ANALYST]: '#8B5CF6',
  [AgentType.SENTIMENT_ANALYST]: '#EC4899',
  [AgentType.NEWS_ANALYST]: '#F97316',
  [AgentType.CAPITAL_FLOW_ANALYST]: '#14B8A6',
  [AgentType.BULL_RESEARCHER]: '#22C55E',
  [AgentType.BEAR_RESEARCHER]: '#EF4444',
  [AgentType.RISK_MANAGER]: '#EAB308',
  [AgentType.TRADER]: '#6366F1',
}

/** Three.js 核心对象 */
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let animationFrameId = 0
let raycaster: THREE.Raycaster
let mouse: THREE.Vector2
let particles: THREE.Points

/** 智能体球体映射 */
const agentMeshes = new Map<string, THREE.Group>()
/** 连接线对象 */
const connectionLines: THREE.Line[] = []
/** 智能体原始 Y 坐标（用于浮动动画） */
const agentBaseY = new Map<string, number>()

/**
 * 获取智能体环形排列位置
 * @param count - 智能体数量
 * @param radius - 环形半径
 * @returns 位置数组
 */
function getAgentPositions(count: number, radius: number = 5): { x: number; y: number }[] {
  const positions: { x: number; y: number }[] = []
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2
    positions.push({
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    })
  }
  return positions
}

/**
 * 获取智能体对应颜色
 * @param type - 智能体类型
 * @returns 十六进制颜色字符串
 */
function getAgentColor(type: AgentType): string {
  return agentColorMap[type] || '#64748B'
}

/**
 * 创建文字精灵（Sprite）
 * @param icon - emoji 图标
 * @param name - 智能体名称
 * @returns Sprite 对象
 */
function createTextSprite(icon: string, name: string): THREE.Sprite {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')!
  canvas.width = 256
  canvas.height = 96

  context.clearRect(0, 0, canvas.width, canvas.height)

  context.fillStyle = 'rgba(15, 23, 42, 0.7)'
  context.beginPath()
  context.roundRect(0, 0, canvas.width, canvas.height, 12)
  context.fill()

  context.font = '28px Arial'
  context.fillStyle = '#ffffff'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(icon, canvas.width / 2, 28)

  context.font = 'bold 18px Arial'
  context.fillStyle = '#e2e8f0'
  context.fillText(name, canvas.width / 2, 66)

  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(2.2, 0.82, 1)

  return sprite
}

/**
 * 创建单个智能体球体组
 * @param agent - 智能体数据
 * @param position - 3D 位置
 * @returns Group 对象
 */
function createAgentOrb(agent: Agent, position: THREE.Vector3): THREE.Group {
  const group = new THREE.Group()
  group.userData = { agentId: agent.id }

  const color = new THREE.Color(getAgentColor(agent.type))

  const geometry = new THREE.SphereGeometry(0.55, 32, 32)
  const material = new THREE.MeshPhongMaterial({
    color: color,
    emissive: color,
    emissiveIntensity: agent.status === AgentStatus.RUNNING ? 0.5 : 0.15,
    transparent: true,
    opacity: 0.92,
    shininess: 80,
  })
  const sphere = new THREE.Mesh(geometry, material)
  sphere.name = 'orb'
  group.add(sphere)

  const glowGeometry = new THREE.SphereGeometry(0.75, 32, 32)
  const glowMaterial = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.15,
  })
  const glow = new THREE.Mesh(glowGeometry, glowMaterial)
  glow.name = 'glow'
  group.add(glow)

  const label = createTextSprite(agent.icon, agent.name)
  label.position.set(0, -1.15, 0)
  group.add(label)

  group.position.copy(position)
  return group
}

/**
 * 创建所有智能体球体
 */
function createAgentOrbs(): void {
  const positions = getAgentPositions(props.agents.length)
  props.agents.forEach((agent, index) => {
    const pos = new THREE.Vector3(positions[index].x, positions[index].y, 0)
    const orb = createAgentOrb(agent, pos)
    scene.add(orb)
    agentMeshes.set(agent.id, orb)
    agentBaseY.set(agent.id, positions[index].y)
  })
}

/**
 * 创建智能体之间的连接线
 */
function createConnections(): void {
  const lineMaterial = new THREE.LineBasicMaterial({
    color: 0x475569,
    transparent: true,
    opacity: 0.25,
  })

  const positions = getAgentPositions(props.agents.length)

  const connections: [number, number][] = [
    [0, 1], [0, 2], [0, 3], [0, 4],
    [1, 5], [2, 5], [3, 6], [4, 6],
    [5, 7], [6, 7],
    [7, 8],
  ]

  connections.forEach(([from, to]) => {
    if (from >= positions.length || to >= positions.length) return
    const points = [
      new THREE.Vector3(positions[from].x, positions[from].y, 0),
      new THREE.Vector3(positions[to].x, positions[to].y, 0),
    ]
    const geometry = new THREE.BufferGeometry().setFromPoints(points)
    const line = new THREE.Line(geometry, lineMaterial.clone())
    scene.add(line)
    connectionLines.push(line)
  })
}

/**
 * 创建粒子背景效果
 */
function createParticles(): void {
  const particleCount = 300
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(particleCount * 3)

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 50
    positions[i * 3 + 1] = (Math.random() - 0.5) * 30
    positions[i * 3 + 2] = (Math.random() - 0.5) * 20 - 10
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

  const material = new THREE.PointsMaterial({
    color: 0x3b82f6,
    size: 0.08,
    transparent: true,
    opacity: 0.5,
    sizeAttenuation: true,
  })

  particles = new THREE.Points(geometry, material)
  scene.add(particles)
}

/**
 * 处理球体点击事件
 * @param event - 鼠标事件
 */
function handleClick(event: MouseEvent): void {
  if (!containerRef.value || !camera || !scene) return

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)

  const meshes: THREE.Object3D[] = []
  agentMeshes.forEach((group) => {
    group.traverse((child) => {
      if (child instanceof THREE.Mesh && child.name === 'orb') {
        meshes.push(child)
      }
    })
  })

  const intersects = raycaster.intersectObjects(meshes, false)

  if (intersects.length > 0) {
    const hit = intersects[0].object
    const parentGroup = hit.parent
    const agentId = parentGroup?.userData?.agentId
    if (agentId) {
      const agent = props.agents.find((a) => a.id === agentId)
      if (agent) {
        selectedAgent.value = agent
      }
    }
  } else {
    selectedAgent.value = null
  }
}

/**
 * 更新单个智能体的视觉状态
 * @param agent - 智能体数据
 */
function updateAgentVisual(agent: Agent): void {
  const group = agentMeshes.get(agent.id)
  if (!group) return

  const orb = group.getObjectByName('orb') as THREE.Mesh | undefined
  const glow = group.getObjectByName('glow') as THREE.Mesh | undefined
  if (!orb) return

  const material = orb.material as THREE.MeshPhongMaterial

  switch (agent.status) {
    case AgentStatus.RUNNING:
    case AgentStatus.INITIALIZING: {
      const color = new THREE.Color(getAgentColor(agent.type))
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 0.5
      if (glow) {
        const glowMat = glow.material as THREE.MeshBasicMaterial
        glowMat.opacity = 0.25
      }
      break
    }
    case AgentStatus.COMPLETED: {
      material.color.setHex(0x22c55e)
      material.emissive.setHex(0x22c55e)
      material.emissiveIntensity = 0.3
      if (glow) {
        const glowMat = glow.material as THREE.MeshBasicMaterial
        glowMat.color.setHex(0x22c55e)
        glowMat.opacity = 0.2
      }
      break
    }
    case AgentStatus.FAILED: {
      material.color.setHex(0xef4444)
      material.emissive.setHex(0xef4444)
      material.emissiveIntensity = 0.5
      if (glow) {
        const glowMat = glow.material as THREE.MeshBasicMaterial
        glowMat.color.setHex(0xef4444)
        glowMat.opacity = 0.3
      }
      break
    }
    default: {
      const color = new THREE.Color(getAgentColor(agent.type))
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 0.15
      if (glow) {
        const glowMat = glow.material as THREE.MeshBasicMaterial
        glowMat.opacity = 0.1
      }
    }
  }
}

/**
 * 动画循环
 */
function animate(): void {
  animationFrameId = requestAnimationFrame(animate)

  const time = Date.now()

  agentMeshes.forEach((group, id) => {
    const agent = props.agents.find((a) => a.id === id)
    if (!agent) return

    if (agent.status === AgentStatus.RUNNING || agent.status === AgentStatus.INITIALIZING) {
      const baseY = agentBaseY.get(id) ?? 0
      group.position.y = baseY + Math.sin(time * 0.003) * 0.12

      const orb = group.getObjectByName('orb') as THREE.Mesh | undefined
      if (orb) {
        const mat = orb.material as THREE.MeshPhongMaterial
        mat.emissiveIntensity = 0.3 + Math.sin(time * 0.005) * 0.2
      }

      const glow = group.getObjectByName('glow') as THREE.Mesh | undefined
      if (glow) {
        const scale = 1.0 + Math.sin(time * 0.004) * 0.15
        glow.scale.set(scale, scale, scale)
      }
    }
  })

  if (particles) {
    particles.rotation.z += 0.0002
  }

  controls.update()
  renderer.render(scene, camera)
}

/**
 * 窗口 resize 自适应
 */
function handleResize(): void {
  if (!containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

/**
 * 初始化 Three.js 场景
 */
function initScene(): void {
  if (!canvasRef.value || !containerRef.value) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0f172a)

  const aspect = width / height
  camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000)
  camera.position.set(0, 0, 14)

  renderer = new THREE.WebGLRenderer({
    canvas: canvasRef.value,
    antialias: true,
    alpha: true,
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 8
  controls.maxDistance = 30
  controls.enablePan = false

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
  scene.add(ambientLight)

  const pointLight1 = new THREE.PointLight(0x3b82f6, 1.5, 50)
  pointLight1.position.set(10, 10, 10)
  scene.add(pointLight1)

  const pointLight2 = new THREE.PointLight(0x8b5cf6, 0.8, 50)
  pointLight2.position.set(-10, -5, 8)
  scene.add(pointLight2)

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()

  createAgentOrbs()
  createConnections()
  createParticles()

  containerRef.value.addEventListener('click', handleClick)

  animate()
}

/**
 * 清理 Three.js 资源
 */
function cleanup(): void {
  cancelAnimationFrame(animationFrameId)

  if (containerRef.value) {
    containerRef.value.removeEventListener('click', handleClick)
  }

  scene?.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.geometry?.dispose()
      if (Array.isArray(object.material)) {
        object.material.forEach((m) => m.dispose())
      } else {
        object.material?.dispose()
      }
    }
  })

  renderer?.dispose()
  controls?.dispose()

  agentMeshes.clear()
  agentBaseY.clear()
  connectionLines.length = 0
}

watch(
  () => props.agents,
  (newAgents) => {
    newAgents.forEach((agent) => {
      updateAgentVisual(agent)
    })
  },
  { deep: true },
)

onMounted(() => {
  initScene()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  cleanup()
})
</script>

<style scoped>
.agent-scene {
  position: relative;
  width: 100%;
  height: 500px;
  background: var(--color-bg-primary);
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.agent-scene canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.scene-hints {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: rgba(0, 0, 0, 0.5);
  padding: 6px 14px;
  border-radius: 2px;
  pointer-events: none;
  user-select: none;
}

.agent-detail-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 260px;
  background: rgba(20, 24, 39, 0.95);
  backdrop-filter: blur(12px);
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  overflow: hidden;
  z-index: 10;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.detail-icon {
  font-size: 24px;
}

.detail-name {
  flex: 1;
  font-weight: 600;
  font-size: 16px;
  color: #f8fafc;
}

.close-btn {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 18px;
  padding: 4px;
  line-height: 1;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #f8fafc;
}

.detail-body {
  padding: 16px;
}

.detail-status,
.detail-progress,
.detail-task {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.label {
  color: #64748b;
  font-size: 13px;
  min-width: 60px;
  flex-shrink: 0;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-badge.status-running {
  color: #f59e0b;
}

.status-badge.status-running .status-dot {
  animation: blink 1s ease-in-out infinite;
}

.status-badge.status-completed {
  color: #22c55e;
}

.status-badge.status-failed {
  color: #ef4444;
}

.status-badge.status-idle {
  color: #10b981;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.progress-ring {
  position: relative;
  width: 60px;
  height: 60px;
  flex-shrink: 0;
}

.progress-ring svg {
  width: 100%;
  height: 100%;
}

.progress-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
}

.task-text {
  color: #e2e8f0;
  font-size: 13px;
}

.detail-output {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.detail-output p {
  margin-top: 8px;
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.6;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
