<template>
  <section class="panel">
    <div class="panel-header">
      <h2>物业报修</h2>
      <el-button size="small" @click="loadTickets">刷新</el-button>
    </div>

    <el-form class="repair-form" label-position="top">
      <el-form-item label="报修房屋（仅限名下有效租约）">
        <el-select v-model="form.propertyId" placeholder="选择房屋" class="full">
          <el-option
            v-for="lease in activeLeases"
            :key="lease.id"
            :label="`${lease.community} · ${lease.layout}（租期至 ${lease.endDate}）`"
            :value="lease.propertyId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="故障类型">
        <el-select v-model="form.faultType" class="full">
          <el-option v-for="type in faultTypes" :key="type" :label="type" :value="type" />
        </el-select>
      </el-form-item>
      <el-form-item label="故障描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请描述故障情况" />
      </el-form-item>
      <el-form-item label="照片链接（可选，多个用逗号分隔）">
        <el-input v-model="form.photosText" placeholder="https://..." />
      </el-form-item>
      <el-button type="success" :loading="submitting" @click="submit">提交报修</el-button>
      <span v-if="!activeLeases.length" class="hint">当前没有生效中的租约，无法报修。</span>
    </el-form>

    <h3>我的工单</h3>
    <el-empty v-if="!tickets.length" description="暂无报修工单" />
    <el-card v-for="ticket in tickets" :key="ticket.id" class="ticket-card" shadow="never">
      <div class="ticket-head">
        <strong>#{{ ticket.id }} {{ ticket.community }} · {{ ticket.faultType }}</strong>
        <el-tag :type="statusTag(ticket.status)">{{ ticket.status }}</el-tag>
      </div>
      <p class="desc">{{ ticket.description }}</p>
      <p class="meta">
        负责人：{{ ticket.assigneeName }} ｜ 预计上门时间：<b>{{ formatDateTime(ticket.expectedVisitAt) }}</b>
        <template v-if="ticket.completedAt"> ｜ 完工时间：{{ formatDateTime(ticket.completedAt) }}</template>
      </p>
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
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { createRepair, getMyContracts, getRepairs } from '../api/client';
import type { Contract, RepairTicket } from '../types/domain';
import { formatDateTime } from '../utils/format';

const faultTypes = ['水电', '门锁', '管道', '家电', '其他'];
const leases = ref<Contract[]>([]);
const tickets = ref<RepairTicket[]>([]);
const submitting = ref(false);
const form = reactive({ propertyId: 0, faultType: '水电', description: '', photosText: '' });

const activeLeases = computed(() => leases.value.filter((lease) => lease.status === '生效中'));

onMounted(async () => {
  leases.value = await getMyContracts();
  if (activeLeases.value.length) form.propertyId = activeLeases.value[0].propertyId;
  await loadTickets();
});

async function loadTickets() {
  tickets.value = await getRepairs();
}

async function submit() {
  if (!form.propertyId) {
    ElMessage.warning('请选择报修房屋');
    return;
  }
  submitting.value = true;
  try {
    const photos = form.photosText.split(',').map((item) => item.trim()).filter(Boolean);
    const ticket = await createRepair({
      propertyId: form.propertyId,
      faultType: form.faultType,
      description: form.description,
      photos,
    });
    ElMessage.success(ticket.merged ? `已合并到原工单 #${ticket.id}` : `工单 #${ticket.id} 已提交，${ticket.assigneeName} 处理中`);
    form.description = '';
    form.photosText = '';
    await loadTickets();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    submitting.value = false;
  }
}

function statusTag(status: string): 'info' | 'warning' | 'success' {
  if (status === '已完工') return 'success';
  if (status === '处理中') return 'warning';
  return 'info';
}
</script>
