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
          <button @click="selectedAgent = null" class="close-btn">x</button>
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
                <circle class="progress-bg" cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="8" />
                <circle class="progress-fill" cx="50" cy="50" r="45" fill="none" :stroke="selectedAgent.color" stroke-width="8" stroke-linecap="round" :stroke-dasharray="283" :stroke-dashoffset="283 - (283 * selectedAgent.progress / 100)" transform="rotate(-90 50 50)" />
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

const statusTextMap: Record<string, string> = {
  [AgentStatus.IDLE]: '空闲',
  [AgentStatus.INITIALIZING]: '初始化',
  [AgentStatus.RUNNING]: '运行中',
  [AgentStatus.WAITING]: '等待中',
  [AgentStatus.COMPLETED]: '已完成',
  [AgentStatus.FAILED]: '失败',
}

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

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let animationFrameId = 0
let raycaster: THREE.Raycaster
let mouse: THREE.Vector2
let particles: THREE.Points
/** 是否自动旋转（鼠标悬停时暂停） */
let autoRotate = true
/** 场景根组（用于整体旋转） */
let sceneGroup: THREE.Group

const agentMeshes = new Map<string, THREE.Group>()
const agentBaseY = new Map<string, number>()
/** 数据流粒子 - 沿连接线移动的光点 */
const dataFlowParticles: Array<{
  mesh: THREE.Mesh
  fromIdx: number
  toIdx: number
  progress: number
  speed: number
  active: boolean
}> = []
/** 连接线定义 */
const connectionDefs: Array<[number, number]> = [
  [0, 1], [0, 2], [0, 3], [0, 4], [0, 5],
  [1, 6], [2, 6], [3, 7], [4, 7], [5, 6], [5, 7],
  [6, 8], [7, 8],
  [8, 9],
]
/** 轨道环 */
const orbitRings: THREE.Mesh[] = []

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

function getAgentColor(type: AgentType): string {
  return agentColorMap[type] || '#64748B'
}

/** 创建文字精灵标签 */
function createTextSprite(icon: string, name: string, status: AgentStatus): THREE.Sprite {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')!
  canvas.width = 256
  canvas.height = 96

  context.clearRect(0, 0, canvas.width, canvas.height)

  // 背景根据状态变化
  const isActive = status === AgentStatus.RUNNING || status === AgentStatus.INITIALIZING
  context.fillStyle = isActive ? 'rgba(59, 130, 246, 0.35)' : 'rgba(15, 23, 42, 0.7)'
  context.beginPath()
  context.roundRect(0, 0, canvas.width, canvas.height, 12)
  context.fill()

  // 运行中时添加边框
  if (isActive) {
    context.strokeStyle = 'rgba(59, 130, 246, 0.6)'
    context.lineWidth = 2
    context.beginPath()
    context.roundRect(1, 1, canvas.width - 2, canvas.height - 2, 12)
    context.stroke()
  }

  context.font = '28px Arial'
  context.fillStyle = '#ffffff'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(icon, canvas.width / 2, 28)

  context.font = 'bold 18px Arial'
  context.fillStyle = isActive ? '#93C5FD' : '#e2e8f0'
  context.fillText(name, canvas.width / 2, 66)

  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(2.2, 0.82, 1)
  return sprite
}

/** 创建旋转光环（运行中时显示） */
function createOrbitRing(color: THREE.Color): THREE.Mesh {
  const geometry = new THREE.TorusGeometry(0.85, 0.02, 8, 48)
  const material = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0,
  })
  const ring = new THREE.Mesh(geometry, material)
  ring.name = 'orbitRing'
  // 随机倾斜角度
  ring.rotation.x = Math.PI * 0.3
  ring.rotation.y = Math.PI * 0.2
  return ring
}

/** 创建脉冲波纹（运行中时从球体向外扩散） */
function createPulseRing(color: THREE.Color): THREE.Mesh {
  const geometry = new THREE.RingGeometry(0.55, 0.58, 32)
  const material = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
  })
  const ring = new THREE.Mesh(geometry, material)
  ring.name = 'pulseRing'
  ring.userData.pulsePhase = Math.random() * Math.PI * 2
  return ring
}

/** 创建单个智能体球体组（增强版） */
function createAgentOrb(agent: Agent, position: THREE.Vector3): THREE.Group {
  const group = new THREE.Group()
  group.userData = { agentId: agent.id }

  const color = new THREE.Color(getAgentColor(agent.type))

  // 核心球体 - 高细分SphereGeometry确保清晰
  const coreGeometry = new THREE.SphereGeometry(0.5, 32, 32)
  const coreMaterial = new THREE.MeshStandardMaterial({
    color: color,
    emissive: color,
    emissiveIntensity: 0.15,
    transparent: true,
    opacity: 0.95,
    roughness: 0.3,
    metalness: 0.6,
  })
  const core = new THREE.Mesh(coreGeometry, coreMaterial)
  core.name = 'orb'
  group.add(core)

  // 线框外壳 - 科技感
  const wireGeometry = new THREE.IcosahedronGeometry(0.6, 2)
  const wireMaterial = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.15,
    wireframe: true,
  })
  const wireframe = new THREE.Mesh(wireGeometry, wireMaterial)
  wireframe.name = 'wireframe'
  group.add(wireframe)

  // 外发光层
  const glowGeometry = new THREE.SphereGeometry(0.75, 16, 16)
  const glowMaterial = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.1,
  })
  const glow = new THREE.Mesh(glowGeometry, glowMaterial)
  glow.name = 'glow'
  group.add(glow)

  // 旋转光环
  const orbitRing = createOrbitRing(color)
  group.add(orbitRing)
  orbitRings.push(orbitRing)

  // 脉冲波纹
  const pulseRing = createPulseRing(color)
  group.add(pulseRing)

  // 文字标签
  const label = createTextSprite(agent.icon, agent.name, agent.status)
  label.position.set(0, -1.2, 0)
  label.name = 'label'
  group.add(label)

  group.position.copy(position)
  return group
}

function createAgentOrbs(): void {
  const positions = getAgentPositions(props.agents.length)
  props.agents.forEach((agent, index) => {
    const pos = new THREE.Vector3(positions[index].x, positions[index].y, 0)
    const orb = createAgentOrb(agent, pos)
    sceneGroup.add(orb)
    agentMeshes.set(agent.id, orb)
    agentBaseY.set(agent.id, positions[index].y)
  })
}

/** 创建连接线（带流动效果） */
function createConnections(): void {
  const positions = getAgentPositions(props.agents.length)

  connectionDefs.forEach(([from, to]) => {
    if (from >= positions.length || to >= positions.length) return

    const fromPos = new THREE.Vector3(positions[from].x, positions[from].y, 0)
    const toPos = new THREE.Vector3(positions[to].x, positions[to].y, 0)

    // 基础连接线
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([fromPos, toPos])
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x475569,
      transparent: true,
      opacity: 0.15,
    })
    const line = new THREE.Line(lineGeometry, lineMaterial)
    sceneGroup.add(line)

    // 数据流粒子 - 沿连接线移动的小光点
    const particleGeometry = new THREE.SphereGeometry(0.04, 6, 6)
    const particleMaterial = new THREE.MeshBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0,
    })
    const particleMesh = new THREE.Mesh(particleGeometry, particleMaterial)
    sceneGroup.add(particleMesh)

    dataFlowParticles.push({
      mesh: particleMesh,
      fromIdx: from,
      toIdx: to,
      progress: Math.random(),
      speed: 0.003 + Math.random() * 0.004,
      active: false,
    })
  })
}

function createParticles(): void {
  const particleCount = 80
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(particleCount * 3)

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 40
    positions[i * 3 + 1] = (Math.random() - 0.5) * 25
    positions[i * 3 + 2] = (Math.random() - 0.5) * 15 - 8
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

  const material = new THREE.PointsMaterial({
    color: 0x3b82f6,
    size: 0.06,
    transparent: true,
    opacity: 0.35,
    sizeAttenuation: true,
  })

  particles = new THREE.Points(geometry, material)
  sceneGroup.add(particles)
}

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

/** 鼠标进入场景时暂停自动旋转 */
function handleMouseEnter(): void {
  autoRotate = false
}

/** 鼠标离开场景时恢复自动旋转 */
function handleMouseLeave(): void {
  autoRotate = true
  selectedAgent.value = null
}

/** 更新智能体视觉状态 */
function updateAgentVisual(agent: Agent): void {
  const group = agentMeshes.get(agent.id)
  if (!group) return

  const orb = group.getObjectByName('orb') as THREE.Mesh | undefined
  const wireframe = group.getObjectByName('wireframe') as THREE.Mesh | undefined
  const glow = group.getObjectByName('glow') as THREE.Mesh | undefined
  const orbitRing = group.getObjectByName('orbitRing') as THREE.Mesh | undefined
  const label = group.getObjectByName('label') as THREE.Sprite | undefined
  if (!orb) return

  const material = orb.material as THREE.MeshStandardMaterial
  const color = new THREE.Color(getAgentColor(agent.type))

  switch (agent.status) {
    case AgentStatus.RUNNING:
    case AgentStatus.INITIALIZING: {
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 0.5
      if (glow) { (glow.material as THREE.MeshBasicMaterial).opacity = 0.25 }
      if (wireframe) { (wireframe.material as THREE.MeshBasicMaterial).opacity = 0.3 }
      if (orbitRing) { (orbitRing.material as THREE.MeshBasicMaterial).opacity = 0.5 }
      break
    }
    case AgentStatus.COMPLETED: {
      material.color.setHex(0x22c55e)
      material.emissive.setHex(0x22c55e)
      material.emissiveIntensity = 0.3
      if (glow) { (glow.material as THREE.MeshBasicMaterial).color.setHex(0x22c55e); (glow.material as THREE.MeshBasicMaterial).opacity = 0.15 }
      if (wireframe) { (wireframe.material as THREE.MeshBasicMaterial).opacity = 0.08 }
      if (orbitRing) { (orbitRing.material as THREE.MeshBasicMaterial).opacity = 0 }
      break
    }
    case AgentStatus.FAILED: {
      material.color.setHex(0xef4444)
      material.emissive.setHex(0xef4444)
      material.emissiveIntensity = 0.5
      if (glow) { (glow.material as THREE.MeshBasicMaterial).color.setHex(0xef4444); (glow.material as THREE.MeshBasicMaterial).opacity = 0.3 }
      if (wireframe) { (wireframe.material as THREE.MeshBasicMaterial).opacity = 0.15; (wireframe.material as THREE.MeshBasicMaterial).color.setHex(0xef4444) }
      if (orbitRing) { (orbitRing.material as THREE.MeshBasicMaterial).opacity = 0 }
      break
    }
    case AgentStatus.WAITING: {
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 0.08
      if (glow) { (glow.material as THREE.MeshBasicMaterial).opacity = 0.05 }
      if (wireframe) { (wireframe.material as THREE.MeshBasicMaterial).opacity = 0.06 }
      if (orbitRing) { (orbitRing.material as THREE.MeshBasicMaterial).opacity = 0 }
      break
    }
    default: {
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 0.15
      if (glow) { (glow.material as THREE.MeshBasicMaterial).opacity = 0.1 }
      if (wireframe) { (wireframe.material as THREE.MeshBasicMaterial).opacity = 0.12 }
      if (orbitRing) { (orbitRing.material as THREE.MeshBasicMaterial).opacity = 0 }
    }
  }

  // 更新标签
  if (label) {
    const newLabel = createTextSprite(agent.icon, agent.name, agent.status)
    label.material = newLabel.material
    label.material.needsUpdate = true
  }
}

/** 判断连接线是否应该激活（两端有运行中的智能体） */
function isConnectionActive(fromIdx: number, toIdx: number): boolean {
  const fromAgent = props.agents[fromIdx]
  const toAgent = props.agents[toIdx]
  if (!fromAgent || !toAgent) return false
  const running = AgentStatus.RUNNING
  const init = AgentStatus.INITIALIZING
  return (
    (fromAgent.status === running || fromAgent.status === init) ||
    (toAgent.status === running || toAgent.status === init)
  )
}

/** 动画循环 */
function animate(): void {
  animationFrameId = requestAnimationFrame(animate)

  const time = Date.now()

  // 自动旋转：像地球一样3D立体旋转
  if (autoRotate && sceneGroup) {
    sceneGroup.rotation.y += 0.005
  }

  const positions = getAgentPositions(props.agents.length)

  agentMeshes.forEach((group, id) => {
    const agent = props.agents.find((a) => a.id === id)
    if (!agent) return

    const orb = group.getObjectByName('orb') as THREE.Mesh | undefined
    const wireframe = group.getObjectByName('wireframe') as THREE.Mesh | undefined
    const glow = group.getObjectByName('glow') as THREE.Mesh | undefined
    const orbitRing = group.getObjectByName('orbitRing') as THREE.Mesh | undefined
    const pulseRing = group.getObjectByName('pulseRing') as THREE.Mesh | undefined

    if (agent.status === AgentStatus.RUNNING || agent.status === AgentStatus.INITIALIZING) {
      // 运行中：浮动 + 脉冲发光 + 旋转线框 + 旋转光环
      const baseY = agentBaseY.get(id) ?? 0
      group.position.y = baseY + Math.sin(time * 0.003) * 0.12

      if (orb) {
        const mat = orb.material as THREE.MeshStandardMaterial
        mat.emissiveIntensity = 0.3 + Math.sin(time * 0.005) * 0.2
        // 核心球体缓慢自转
        orb.rotation.y += 0.008
        orb.rotation.x += 0.003
      }

      if (wireframe) {
        // 线框反向旋转
        wireframe.rotation.y -= 0.012
        wireframe.rotation.z += 0.006
        const wireMat = wireframe.material as THREE.MeshBasicMaterial
        wireMat.opacity = 0.2 + Math.sin(time * 0.004) * 0.1
      }

      if (glow) {
        const scale = 1.0 + Math.sin(time * 0.004) * 0.15
        glow.scale.set(scale, scale, scale)
      }

      if (orbitRing) {
        orbitRing.rotation.z += 0.02
        const ringMat = orbitRing.material as THREE.MeshBasicMaterial
        ringMat.opacity = 0.4 + Math.sin(time * 0.003) * 0.15
      }

      // 脉冲波纹 - 从球体向外扩散
      if (pulseRing) {
        const phase = (pulseRing.userData.pulsePhase + time * 0.002) % (Math.PI * 2)
        const pulseScale = 1.0 + (phase / (Math.PI * 2)) * 1.5
        pulseRing.scale.set(pulseScale, pulseScale, 1)
        const pulseMat = pulseRing.material as THREE.MeshBasicMaterial
        pulseMat.opacity = Math.max(0, 0.4 * (1 - phase / (Math.PI * 2)))
      }

    } else if (agent.status === AgentStatus.COMPLETED) {
      // 完成：轻微呼吸
      if (orb) {
        const mat = orb.material as THREE.MeshStandardMaterial
        mat.emissiveIntensity = 0.2 + Math.sin(time * 0.002) * 0.05
      }
      if (wireframe) { wireframe.rotation.y += 0.002 }
      if (pulseRing) { (pulseRing.material as THREE.MeshBasicMaterial).opacity = 0 }

    } else if (agent.status === AgentStatus.WAITING) {
      // 等待：微弱呼吸
      if (orb) {
        const mat = orb.material as THREE.MeshStandardMaterial
        mat.emissiveIntensity = 0.05 + Math.sin(time * 0.001) * 0.03
      }
      if (pulseRing) { (pulseRing.material as THREE.MeshBasicMaterial).opacity = 0 }

    } else if (agent.status === AgentStatus.FAILED) {
      // 失败：抖动
      const baseY = agentBaseY.get(id) ?? 0
      group.position.y = baseY + Math.sin(time * 0.05) * 0.05
      if (pulseRing) { (pulseRing.material as THREE.MeshBasicMaterial).opacity = 0 }

    } else {
      // 空闲：轻微浮动
      const baseY = agentBaseY.get(id) ?? 0
      group.position.y = baseY + Math.sin(time * 0.001 + agentBaseY.size) * 0.03
      if (wireframe) { wireframe.rotation.y += 0.001 }
      if (pulseRing) { (pulseRing.material as THREE.MeshBasicMaterial).opacity = 0 }
    }
  })

  // 数据流粒子动画
  dataFlowParticles.forEach((particle) => {
    const active = isConnectionActive(particle.fromIdx, particle.toIdx)
    particle.active = active

    if (active) {
      particle.progress += particle.speed
      if (particle.progress > 1) particle.progress = 0

      const fromPos = positions[particle.fromIdx]
      const toPos = positions[particle.toIdx]
      if (fromPos && toPos) {
        const x = fromPos.x + (toPos.x - fromPos.x) * particle.progress
        const y = fromPos.y + (toPos.y - fromPos.y) * particle.progress
        particle.mesh.position.set(x, y, 0)

        const mat = particle.mesh.material as THREE.MeshBasicMaterial
        // 粒子在中间最亮，两端渐隐
        const brightness = Math.sin(particle.progress * Math.PI)
        mat.opacity = brightness * 0.8
        const scale = 0.8 + brightness * 0.5
        particle.mesh.scale.set(scale, scale, scale)
      }
    } else {
      (particle.mesh.material as THREE.MeshBasicMaterial).opacity = 0
    }
  })

  // 背景粒子缓慢旋转
  if (particles) {
    particles.rotation.z += 0.0002
  }

  controls.update()
  renderer.render(scene, camera)
}

function handleResize(): void {
  if (!containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function initScene(): void {
  if (!canvasRef.value || !containerRef.value) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0f172a)

  // 添加雾效增加深度感
  scene.fog = new THREE.FogExp2(0x0f172a, 0.02)

  // 创建场景根组（用于整体旋转）
  sceneGroup = new THREE.Group()
  // 地球自转轴倾斜效果（约23.5度）
  sceneGroup.rotation.x = 0.15
  scene.add(sceneGroup)

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
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 8
  controls.maxDistance = 30
  controls.enablePan = false

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(5, 10, 7)
  scene.add(directionalLight)

  const pointLight1 = new THREE.PointLight(0x3b82f6, 1.2, 50)
  pointLight1.position.set(10, 10, 10)
  scene.add(pointLight1)

  const pointLight2 = new THREE.PointLight(0x8b5cf6, 0.6, 50)
  pointLight2.position.set(-10, -5, 8)
  scene.add(pointLight2)

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()

  createAgentOrbs()
  createConnections()
  createParticles()

  containerRef.value.addEventListener('click', handleClick)
  containerRef.value.addEventListener('mouseenter', handleMouseEnter)
  containerRef.value.addEventListener('mouseleave', handleMouseLeave)

  animate()
}

function cleanup(): void {
  cancelAnimationFrame(animationFrameId)

  if (containerRef.value) {
    containerRef.value.removeEventListener('click', handleClick)
    containerRef.value.removeEventListener('mouseenter', handleMouseEnter)
    containerRef.value.removeEventListener('mouseleave', handleMouseLeave)
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
  dataFlowParticles.length = 0
  orbitRings.length = 0
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

.detail-icon { font-size: 24px; }

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

.close-btn:hover { color: #f8fafc; }

.detail-body { padding: 16px; }

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

.status-badge.status-running { color: #f59e0b; }
.status-badge.status-running .status-dot { animation: blink 1s ease-in-out infinite; }
.status-badge.status-completed { color: #22c55e; }
.status-badge.status-failed { color: #ef4444; }
.status-badge.status-idle { color: #10b981; }

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

.progress-ring svg { width: 100%; height: 100%; }

.progress-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
}

.task-text { color: #e2e8f0; font-size: 13px; }

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
