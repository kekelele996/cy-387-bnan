<template>
  <section class="panel">
    <div class="panel-header">
      <h2>物业工作台</h2>
      <el-button size="small" :loading="loading" @click="refresh">刷新</el-button>
    </div>

    <el-empty v-if="!tickets.length" description="暂无相关工单" />
    <el-card v-for="ticket in tickets" :key="ticket.id" class="ticket-card" shadow="never">
      <div class="ticket-head">
        <strong>#{{ ticket.id }} {{ ticket.community }} · {{ ticket.faultType }}</strong>
        <el-tag :type="statusTag(ticket.status)">{{ ticket.status }}</el-tag>
      </div>
      <p class="desc">{{ ticket.description }}</p>
      <p class="meta">
        报修人：{{ ticket.tenantName }} ｜ 负责人：{{ ticket.assigneeName }} ｜
        预计上门时间：<b>{{ formatDateTime(ticket.expectedVisitAt) }}</b>
      </p>

      <div class="actions">
        <el-button
          v-if="ticket.status === '待接单'"
          type="primary"
          size="small"
          :loading="acting"
          @click="accept(ticket.id)"
        >接单</el-button>
        <template v-if="ticket.status === '处理中' && ticket.assigneeId === currentUserId">
          <el-select
            v-model="reassignTargets[ticket.id]"
            size="small"
            placeholder="选择转派对象"
            class="reassign-select"
          >
            <el-option
              v-for="staff in qualifiedTargets(ticket.faultType)"
              :key="staff.id"
              :label="`${staff.name}（未完成 ${staff.unfinishedCount} 单）`"
              :value="staff.id"
            />
          </el-select>
          <el-button size="small" :loading="acting" @click="reassign(ticket.id)">转派</el-button>
          <el-button type="success" size="small" :loading="acting" @click="complete(ticket.id)">完工</el-button>
        </template>
      </div>

      <el-timeline class="trail">
        <el-timeline-item
          v-for="log in ticket.logs"
          :key="log.id"
          :timestamp="formatDateTime(log.createdAt)"
          size="small"
        >
          {{ log.action }} · {{ log.operatorName }}<span v-if="log.note">（{{ log.note }}）</span>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { acceptRepair, completeRepair, getRepairStaff, getRepairs, reassignRepair } from '../api/client';
import { session } from '../store/session';
import type { RepairTicket, StaffOption } from '../types/domain';
import { formatDateTime } from '../utils/format';

const tickets = ref<RepairTicket[]>([]);
const staffOptions = ref<StaffOption[]>([]);
const reassignTargets = reactive<Record<number, number | undefined>>({});
const loading = ref(false);
const acting = ref(false);

const currentUserId = computed(() => session.user?.id ?? 0);
const currentName = computed(() => session.user?.name ?? '');

onMounted(async () => {
  staffOptions.value = await getRepairStaff();
  await refresh();
});

async function refresh() {
  loading.value = true;
  try {
    const [ticketList, staffList] = await Promise.all([getRepairs(), getRepairStaff()]);
    tickets.value = ticketList;
    staffOptions.value = staffList;
  } finally {
    loading.value = false;
  }
}

function qualifiedTargets(faultType: string): StaffOption[] {
  return staffOptions.value.filter(
    (staff) => staff.name !== currentName.value && staff.qualifications.includes(faultType),
  );
}

async function run(action: () => Promise<RepairTicket>, success: string) {
  acting.value = true;
  try {
    const ticket = await action();
    ElMessage.success(`工单 #${ticket.id} ${success}`);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    acting.value = false;
    await refresh();
  }
}

async function accept(id: number) {
  await run(() => acceptRepair(id), '接单成功');
}

async function reassign(id: number) {
  const target = reassignTargets[id];
  if (!target) {
    ElMessage.warning('请选择转派对象');
    return;
  }
  await run(() => reassignRepair(id, target, ''), '已转派');
  reassignTargets[id] = undefined;
}

async function complete(id: number) {
  try {
    await ElMessageBox.confirm('确认该工单已维修完成？', '完工确认', { type: 'warning' });
  } catch {
    return;
  }
  await run(() => completeRepair(id, ''), '已完工');
}

function statusTag(status: string): 'info' | 'warning' | 'success' {
  if (status === '已完工') return 'success';
  if (status === '处理中') return 'warning';
  return 'info';
}
</script>
