import { createApp } from 'vue'
import AgentStatusBadge from '@/components/common/AgentStatusBadge.vue'
import ProgressRing from '@/components/common/ProgressRing.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import AgentCard from '@/components/agents/AgentCard.vue'
import AgentOutput from '@/components/agents/AgentOutput.vue'
import LogConsole from '@/components/dashboard/LogConsole.vue'
import ResultCard from '@/components/dashboard/ResultCard.vue'

const app = createApp({
  template: '<div>Component Test</div>',
})

app.component('AgentStatusBadge', AgentStatusBadge)
app.component('ProgressRing', ProgressRing)
app.component('LoadingSpinner', LoadingSpinner)
app.component('AgentCard', AgentCard)
app.component('AgentOutput', AgentOutput)
app.component('LogConsole', LogConsole)
app.component('ResultCard', ResultCard)

app.mount('#app')
