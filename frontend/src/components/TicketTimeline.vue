<template>
  <el-timeline class="ticket-timeline">
    <el-timeline-item
      v-for="log in logs"
      :key="log.id"
      :timestamp="formatDateTime(log.created_at)"
      placement="top"
      :type="timelineType(log.action)"
    >
      <strong>{{ log.action }}</strong>
      <span class="operator">· {{ log.operatorName }}</span>
      <span v-if="log.from_status || log.to_status" class="status-flow">
        {{ log.from_status || '—' }} → {{ log.to_status || '—' }}
      </span>
      <div v-if="log.note" class="note">{{ log.note }}</div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { TicketLog } from '../types/domain';
import { formatDateTime } from '../constants/repair';

defineProps<{ logs: TicketLog[] }>();

function timelineType(action: string): 'primary' | 'success' | 'warning' | 'info' {
  if (action === '完工') return 'success';
  if (action === '接单') return 'primary';
  if (action === '转派') return 'warning';
  return 'info';
}
</script>

<style scoped>
.ticket-timeline { padding: 8px 0 0; }
.operator { color: #6b778c; margin-left: 6px; }
.status-flow { margin-left: 10px; font-size: 12px; color: #8a93a5; }
.note { color: #4e5969; font-size: 13px; margin-top: 2px; }
</style>
