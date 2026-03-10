import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRoute } from 'vue-router'

import {
  fetchWorkspaceSummary,
  getErrorMessage,
  restartOpenClawService,
  restartWorkspaceRuntime,
  saveAgentConfig,
  saveNanobotConfig,
  saveOpenClawChannelConfig,
  saveOpenClawConfig,
  saveProviderConfig,
  startOpenClawService,
  startWorkspaceRuntime,
  stopOpenClawService,
  stopWorkspaceRuntime,
  updateWorkspaceName,
} from '../api'
import { useAuthStore } from '../stores/auth'
import type { WorkspaceSummary } from '../types'

export type RuntimeAction = 'start' | 'restart' | 'stop'

function resetObject(target: Record<string, unknown>) {
  for (const key of Object.keys(target)) {
    delete target[key]
  }
}

export function useWorkspaceDetail() {
  const message = useMessage()
  const route = useRoute()
  const authStore = useAuthStore()

  const workspaceId = computed(() => Number(route.params.id))
  const summary = ref<WorkspaceSummary | null>(null)
  const workspaceNameInput = ref('')
  const savingNanobot = ref(false)
  const savingAgent = ref(false)
  const savingProviders = ref(false)
  const savingOpenClaw = ref(false)
  const savingOpenClawChannel = ref(false)
  const openclawRawJson = ref('')
  const selectedProviderKey = ref<string | null>(null)

  const nanobotValues = reactive<Record<string, Record<string, unknown>>>({})
  const agentValues = reactive<Record<string, unknown>>({})
  const providerValues = reactive<Record<string, Record<string, unknown>>>({})
  const openclawValues = reactive<Record<string, unknown>>({})
  const openclawChannelValues = reactive<Record<string, unknown>>({})

  const isBaseWorkspace = computed(() => summary.value?.workspace.workspace_type === 'base')
  const runtimeStatus = computed(() => summary.value?.runtime_status ?? null)
  const activationTagType = computed(() => {
    switch (summary.value?.workspace.activation_state) {
      case 'active':
        return 'success'
      case 'error':
        return 'error'
      default:
        return 'default'
    }
  })
  const runtimeTagType = computed(() => {
    switch (runtimeStatus.value?.state) {
      case 'running':
      case 'configured':
        return 'success'
      case 'error':
        return 'error'
      case 'starting':
      case 'stopping':
        return 'warning'
      default:
        return 'default'
    }
  })

  function providerHasValues(sectionKey: string) {
    const values = providerValues[sectionKey]
    if (!values) {
      return false
    }
    return Object.values(values).some((value) => typeof value === 'string' && value.trim().length > 0)
  }

  function resolveDefaultProviderKey(nextSummary: WorkspaceSummary) {
    const sections = nextSummary.nanobot_provider_config?.schema.sections || []
    if (sections.length === 0) {
      return null
    }
    const agentProvider =
      typeof nextSummary.nanobot_agent_config?.values?.provider === 'string' ? nextSummary.nanobot_agent_config.values.provider : ''
    if (agentProvider && agentProvider !== 'auto' && sections.some((section) => section.key === agentProvider)) {
      return agentProvider
    }
    const firstConfigured = sections.find((section) => providerHasValues(section.key))
    return firstConfigured?.key ?? sections[0].key
  }

  function populateForms(nextSummary: WorkspaceSummary) {
    workspaceNameInput.value = nextSummary.workspace.name

    for (const key of Object.keys(nanobotValues)) {
      delete nanobotValues[key]
    }
    if (nextSummary.nanobot_config) {
      for (const [section, values] of Object.entries(nextSummary.nanobot_config.values)) {
        nanobotValues[section] = { ...(values as Record<string, unknown>) }
      }
    }

    resetObject(agentValues)
    if (nextSummary.nanobot_agent_config) {
      Object.assign(agentValues, nextSummary.nanobot_agent_config.values)
    }

    for (const key of Object.keys(providerValues)) {
      delete providerValues[key]
    }
    if (nextSummary.nanobot_provider_config) {
      for (const [section, values] of Object.entries(nextSummary.nanobot_provider_config.values)) {
        providerValues[section] = { ...(values as Record<string, unknown>) }
      }
    }
    selectedProviderKey.value = resolveDefaultProviderKey(nextSummary)

    resetObject(openclawValues)
    if (nextSummary.openclaw_config) {
      Object.assign(openclawValues, nextSummary.openclaw_config.values)
      openclawRawJson.value = nextSummary.openclaw_config.raw_json5
    } else {
      openclawRawJson.value = ''
    }

    resetObject(openclawChannelValues)
    if (nextSummary.openclaw_channel_config) {
      Object.assign(openclawChannelValues, nextSummary.openclaw_channel_config.values)
    }
  }

  async function refreshSummary() {
    try {
      const data = await fetchWorkspaceSummary(workspaceId.value)
      summary.value = data
      populateForms(data)
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function handleRename() {
    try {
      await updateWorkspaceName(workspaceId.value, workspaceNameInput.value)
      message.success('工作区已重命名')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function handleSaveNanobot() {
    savingNanobot.value = true
    try {
      await saveNanobotConfig(workspaceId.value, nanobotValues)
      message.success('Nanobot 配置已保存')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      savingNanobot.value = false
    }
  }

  async function handleSaveAgent() {
    savingAgent.value = true
    try {
      await saveAgentConfig(workspaceId.value, agentValues)
      message.success('Agent Defaults 已保存')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      savingAgent.value = false
    }
  }

  async function handleSaveProviders() {
    savingProviders.value = true
    try {
      await saveProviderConfig(workspaceId.value, providerValues)
      message.success('Providers 配置已保存')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      savingProviders.value = false
    }
  }

  async function handleSaveOpenClaw() {
    savingOpenClaw.value = true
    try {
      await saveOpenClawConfig(workspaceId.value, openclawValues, openclawRawJson.value)
      message.success('OpenClaw 配置已保存')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      savingOpenClaw.value = false
    }
  }

  async function handleSaveOpenClawChannel() {
    savingOpenClawChannel.value = true
    try {
      await saveOpenClawChannelConfig(workspaceId.value, openclawChannelValues)
      message.success('飞书账号配置已保存')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      savingOpenClawChannel.value = false
    }
  }

  async function handleWorkspaceRuntimeAction(action: RuntimeAction) {
    try {
      if (action === 'start') {
        await startWorkspaceRuntime(workspaceId.value)
      } else if (action === 'restart') {
        await restartWorkspaceRuntime(workspaceId.value)
      } else {
        await stopWorkspaceRuntime(workspaceId.value)
      }
      message.success(action === 'start' ? '已发送激活命令' : action === 'restart' ? '已发送重启命令' : '已发送停用命令')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function handleOpenClawServiceAction(action: RuntimeAction) {
    try {
      if (action === 'start') {
        await startOpenClawService()
      } else if (action === 'restart') {
        await restartOpenClawService()
      } else {
        await stopOpenClawService()
      }
      message.success(action === 'start' ? '已启动共享 OpenClaw 服务' : action === 'restart' ? '已重启共享 OpenClaw 服务' : '已停止共享 OpenClaw 服务')
      await refreshSummary()
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  onMounted(async () => {
    await authStore.ensureLoaded()
    await refreshSummary()
  })

  watch(workspaceId, () => {
    void refreshSummary()
  })

  return {
    activationTagType,
    handleOpenClawServiceAction,
    handleRename,
    handleSaveAgent,
    handleSaveNanobot,
    handleSaveOpenClaw,
    handleSaveOpenClawChannel,
    handleSaveProviders,
    handleWorkspaceRuntimeAction,
    isAdmin: authStore.isAdmin,
    isBaseWorkspace,
    nanobotValues,
    openclawChannelValues,
    openclawRawJson,
    openclawValues,
    providerValues,
    refreshSummary,
    runtimeStatus,
    runtimeTagType,
    savingAgent,
    savingNanobot,
    savingOpenClaw,
    savingOpenClawChannel,
    savingProviders,
    selectedProviderKey,
    summary,
    workspaceNameInput,
    agentValues,
  }
}
