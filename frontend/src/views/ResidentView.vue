<template>
  <main class="page">
    <header class="topbar">
      <div>
        <h1>住户报修台</h1>
        <p>为名下有有效租约的房屋提交报修，跟踪维修进度。</p>
      </div>
      <div class="user-box">
        <el-tag>{{ user?.username }}（租客）</el-tag>
        <el-button text @click="logout">退出登录</el-button>
      </div>
    </header>

    <el-card class="form-card">
      <template #header><strong>提交报修</strong></template>
      <el-form :model="form" label-width="92px" @submit.prevent>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="报修房屋" required>
              <el-select v-model="form.houseId" placeholder="选择名下有效租约房屋" style="width: 100%">
                <el-option
                  v-for="house in houses"
                  :key="house.id"
                  :label="`${house.community} ${house.layout}`"
                  :value="house.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="故障类型" required>
              <el-select v-model="form.faultType" style="width: 100%">
                <el-option v-for="fault in FAULT_TYPES" :key="fault" :label="fault" :value="fault" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="故障照片">
              <el-upload :auto-upload="false" :show-file-list="true" :limit="1" :on-change="onPhotoChange" :on-remove="() => (form.photo = null)">
                <el-button>选择照片</el-button>
              </el-upload>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="故障描述" required>
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="请描述故障现象、位置等信息" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">提交工单</el-button>
          <el-button @click="loadAll">刷新</el-button>
          <span v-if="!houses.length" class="hint">您名下暂无有效租约，不能提交报修。</span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <div class="card-header">
          <strong>我的工单</strong>
          <el-tag type="info">共 {{ tickets.length }} 张</el-tag>
        </div>
      </template>
      <el-table :data="tickets" stripe v-loading="loading">
        <el-table-column prop="id" label="工单号" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="房屋 / 故障" min-width="180">
          <template #default="{ row }">
            <div>{{ row.houseLabel }}</div>
            <el-tag size="small">{{ row.faultType }}</el-tag>
            <el-tag v-if="row.merged" size="small" type="warning">已合并</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="责任人" width="120">
          <template #default="{ row }">{{ row.assigneeName ?? '待分配' }}</template>
        </el-table-column>
        <el-table-column label="预计上门时间" width="170">
          <template #default="{ row }">
            <span :class="{ visit: row.estimatedVisitAt }">{{ formatDateTime(row.estimatedVisitAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button size="small" @click="openLogs(row)">处理轨迹</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TicketLogsDialog v-model="logsVisible" :logs="activeLogs" />
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import type { UploadFile } from 'element-plus';
import { createRepair, listMyTickets } from '../api/repair';
import { request } from '../api/client';
import { useAuth } from '../stores/auth';
import { FAULT_TYPES, formatDateTime, statusTagType } from '../constants/repair';
import type { HouseItem, RepairTicket, TicketLog } from '../types/domain';
import TicketLogsDialog from '../components/TicketLogsDialog.vue';
import { useRouter } from 'vue-router';

const { user, logout: authLogout } = useAuth();
const router = useRouter();

const houses = ref<HouseItem[]>([]);
const tickets = ref<RepairTicket[]>([]);
const loading = ref(false);
const submitting = ref(false);
const logsVisible = ref(false);
const activeLogs = ref<TicketLog[]>([]);

const form = reactive({
  houseId: undefined as number | undefined,
  faultType: FAULT_TYPES[0] as string,
  description: '',
  photo: null as File | null,
});

onMounted(loadAll);

async function loadAll() {
  loading.value = true;
  try {
    const [houseList, ticketList] = await Promise.all([
      request<HouseItem[]>('/repairs/my-houses/'),
      listMyTickets(),
    ]);
    houses.value = houseList;
    tickets.value = ticketList;
    if (!form.houseId && houses.value.length) form.houseId = houses.value[0].id;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载失败');
  } finally {
    loading.value = false;
  }
}

function onPhotoChange(file: UploadFile) {
  form.photo = file.raw ?? null;
}

async function submit() {
  if (!form.houseId) {
    ElMessage.warning('请选择名下有有效租约的房屋');
    return;
  }
  if (form.description.trim().length < 2) {
    ElMessage.warning('请填写至少 2 个字的故障描述');
    return;
  }
  submitting.value = true;
  try {
    const ticket = await createRepair({
      houseId: form.houseId,
      faultType: form.faultType,
      description: form.description.trim(),
      photo: form.photo,
    });
    ElMessage.success(ticket.merged ? `同类型故障未关闭，已合并到工单 #${ticket.id}` : `工单 #${ticket.id} 已提交`);
    form.description = '';
    form.photo = null;
    await loadAll();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '报修提交失败');
  } finally {
    submitting.value = false;
  }
}

function openLogs(row: RepairTicket) {
  activeLogs.value = row.logs;
  logsVisible.value = true;
}

function logout() {
  authLogout();
  router.replace({ name: 'login' });
}
</script>

<style scoped>
@import '../styles/portal.css';
</style>
