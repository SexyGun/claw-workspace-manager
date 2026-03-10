<template>
  <n-descriptions label-placement="left" :column="1" bordered>
    <n-descriptions-item label="状态">{{ status?.state ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="范围">{{ status?.scope ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="控制器">{{ status?.controller_kind ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="Unit">{{ status?.unit_name ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="PID">{{ status?.process_id ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="监听端口">{{ status?.listen_port ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="配置文件">{{ status?.config_path ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="工作区目录">{{ status?.workspace_path ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="需要重启">{{ status?.needs_restart ? 'true' : 'false' }}</n-descriptions-item>
    <n-descriptions-item label="启动时间">{{ status?.started_at ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="停止时间">{{ status?.stopped_at ?? '-' }}</n-descriptions-item>
    <n-descriptions-item label="最近错误">{{ status?.last_error ?? '-' }}</n-descriptions-item>
  </n-descriptions>
</template>

<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import type { RuntimeStatus } from '../../types'

defineProps<{
  status: RuntimeStatus | null | undefined
}>()
</script>
