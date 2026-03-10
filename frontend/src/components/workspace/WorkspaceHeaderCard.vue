<template>
  <n-card :bordered="false" class="workspace-header">
    <n-space justify="space-between" align="start" wrap>
      <div>
        <div class="eyebrow">工作区详情</div>
        <n-h2 style="margin: 8px 0 10px">{{ summary.workspace.name }}</n-h2>
        <n-space>
          <n-tag type="warning">{{ summary.workspace.status }}</n-tag>
          <n-tag :type="summary.workspace.workspace_type === 'openclaw' ? 'info' : 'success'">
            {{ summary.workspace.workspace_type }}
          </n-tag>
          <template v-if="isBaseWorkspace">
            <n-tag :type="activationTagType">
              {{ summary.workspace.activation_state ?? 'inactive' }}
            </n-tag>
            <n-tag v-if="summary.workspace.listen_port" type="info">
              port {{ summary.workspace.listen_port }}
            </n-tag>
          </template>
          <n-tag v-else :type="runtimeTagType">{{ runtimeStatus?.state ?? 'unknown' }}</n-tag>
        </n-space>
        <div class="path-text">
          <n-text depth="3">{{ summary.workspace.host_path }}</n-text>
        </div>
      </div>
      <n-space vertical align="end">
        <n-input
          :value="workspaceNameInput"
          placeholder="请输入工作区名称"
          @update:value="emit('update:workspaceNameInput', $event)"
        />
        <n-button type="primary" @click="emit('rename')">重命名工作区</n-button>
        <n-space v-if="isBaseWorkspace">
          <n-button secondary @click="emit('workspace-runtime-action', 'start')">激活</n-button>
          <n-button secondary @click="emit('workspace-runtime-action', 'restart')">重启</n-button>
          <n-button tertiary @click="emit('workspace-runtime-action', 'stop')">停用</n-button>
          <n-button quaternary @click="emit('refresh')">刷新</n-button>
        </n-space>
        <n-button v-else quaternary @click="emit('refresh')">刷新</n-button>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup lang="ts">
import { NButton, NCard, NH2, NInput, NSpace, NTag, NText } from 'naive-ui'

import type { RuntimeStatus, WorkspaceSummary } from '../../types'
import type { RuntimeAction } from '../../composables/useWorkspaceDetail'

type TagType = 'default' | 'error' | 'info' | 'primary' | 'success' | 'warning'

defineProps<{
  activationTagType: TagType
  isBaseWorkspace: boolean
  runtimeStatus: RuntimeStatus | null
  runtimeTagType: TagType
  summary: WorkspaceSummary
  workspaceNameInput: string
}>()

const emit = defineEmits<{
  (event: 'refresh'): void
  (event: 'rename'): void
  (event: 'update:workspaceNameInput', value: string): void
  (event: 'workspace-runtime-action', action: RuntimeAction): void
}>()
</script>

<style scoped>
.eyebrow {
  color: #fb923c;
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.path-text {
  margin-top: 12px;
}
</style>
