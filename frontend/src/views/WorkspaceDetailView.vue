<template>
  <app-shell>
    <n-space v-if="detail.summary.value" vertical size="large">
      <workspace-header-card
        :summary="detail.summary.value"
        :workspace-name-input="detail.workspaceNameInput.value"
        :is-base-workspace="detail.isBaseWorkspace.value"
        :activation-tag-type="detail.activationTagType.value"
        @refresh="detail.refreshSummary"
        @rename="detail.handleRename"
        @update:workspace-name-input="detail.workspaceNameInput.value = $event"
        @workspace-runtime-action="detail.handleWorkspaceRuntimeAction"
      />

      <base-workspace-panels
        v-if="detail.isBaseWorkspace.value"
        :summary="detail.summary.value"
        :nanobot-values="detail.nanobotValues"
        :agent-values="detail.agentValues"
        :provider-values="detail.providerValues"
        :selected-provider-key="detail.selectedProviderKey.value"
        :saving-nanobot="detail.savingNanobot.value"
        :saving-agent="detail.savingAgent.value"
        :saving-providers="detail.savingProviders.value"
        @save-nanobot="detail.handleSaveNanobot"
        @save-agent="detail.handleSaveAgent"
        @save-providers="detail.handleSaveProviders"
        @update:selected-provider-key="detail.selectedProviderKey.value = $event"
      />

      <open-claw-panels
        v-else
        :summary="detail.summary.value"
        :openclaw-values="detail.openclawValues"
        :openclaw-channel-values="detail.openclawChannelValues"
        :openclaw-raw-json="detail.openclawRawJson.value"
        :saving-open-claw="detail.savingOpenClaw.value"
        :saving-open-claw-channel="detail.savingOpenClawChannel.value"
        :is-admin="detail.isAdmin.value"
        @save-open-claw="detail.handleSaveOpenClaw"
        @save-open-claw-channel="detail.handleSaveOpenClawChannel"
        @service-action="detail.handleOpenClawServiceAction"
        @update:openclaw-raw-json="detail.openclawRawJson.value = $event"
      />
    </n-space>

    <n-spin v-else size="large" />
  </app-shell>
</template>

<script setup lang="ts">
import { NSpace, NSpin } from 'naive-ui'

import AppShell from '../components/AppShell.vue'
import BaseWorkspacePanels from '../components/workspace/BaseWorkspacePanels.vue'
import OpenClawPanels from '../components/workspace/OpenClawPanels.vue'
import WorkspaceHeaderCard from '../components/workspace/WorkspaceHeaderCard.vue'
import { useWorkspaceDetail } from '../composables/useWorkspaceDetail'

const detail = useWorkspaceDetail()
</script>
