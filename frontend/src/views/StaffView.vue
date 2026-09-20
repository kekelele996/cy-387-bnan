<template>
  <main class="page">
    <header class="topbar">
      <div>
        <h1>物业工作台</h1>
        <p>
          当前账号 {{ user?.username }}，资质：
          <el-tag v-for="fault in user?.qualified_faults ?? []" :key="fault" size="small" class="qual-tag">{{ fault }}</el-tag>
        </p>
      </div>
      <div class="user-box">
        <el-radio-group v-model="statusFilter" size="small" @change="loadTickets">
          <el-radio-button label="open">未关闭</el-radio-button>
          <el-radio-button label="待受理">待受理</el-radio-button>
          <el-radio-button label="处理中">处理中</el-radio-button>
          <el-radio-button label="已完成">已完成</el-radio-button>
        </el-radio-group>
        <el-select v-model="faultFilter" placeholder="全部故障" clearable size="small" style="width: 130px" @change="loadTickets">
          <el-option v-for="fault in FAULT_TYPES" :key="fault" :label="fault" :value="fault" />
        </el-select>
        <el-button size="small" @click="loadTickets">刷新</el-button>
        <el-button text @click="logout">退出登录</el-button>
      </div>
    </header>

    <el-card>
      <el-table :data="tickets" stripe v-loading="loading" row-key="id">
        <el-table-column prop="id" label="工单号" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="房屋 / 故障" min-width="170">
          <template #default="{ row }">
            <div>{{ row.houseLabel }}</div>
            <div class="sub">
              <el-tag size="small">{{ row.faultType }}</el-tag>
              <span class="reporter">报修人：{{ row.reporterName }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态 / 版本" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
            <div class="version">v{{ row.version }}</div>
          </template>
        </el-table-column>
        <el-table-column label="当前责任人" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.assigneeId === user?.id" type="success">我</el-tag>
            <span>{{ row.assigneeName ?? '待分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="预计上门" width="160">
          <template #default="{ row }">{{ formatDateTime(row.estimatedVisitAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="270">
          <template #default="{ row }">
            <el-button
              v-if="row.status === '待受理'"
              type="primary"
              size="small"
              @click="handleAccept(row)"
            >
              接单
            </el-button>
            <template v-if="row.status === '处理中'">
              <el-button
                type="warning"
                size="small"
                :disabled="row.assigneeId !== user?.id"
                @click="openTransfer(row)"
              >
                转派
              </el-button>
              <el-button
                type="success"
                size="small"
                :disabled="row.assigneeId !== user?.id"
                @click="handleComplete(row)"
              >
                完工
              </el-button>
            </template>
            <el-button size="small" @click="openLogs(row)">轨迹</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 转派对话框 -->
    <el-dialog v-model="transferVisible" title="转派工单" width="460px">
      <el-form label-width="100px">
        <el-form-item label="当前工单">
          <span>#{{ transferTarget?.id }} {{ transferTarget?.faultType }} · {{ transferTarget?.houseLabel }}</span>
        </el-form-item>
        <el-form-item label="转给谁">
          <el-select v-model="transferForm.assigneeId" placeholder="选择合格物业人员" style="width: 100%">
            <el-option
              v-for="staff in eligibleStaff"
              :key="staff.id"
              :label="`${staff.username}（未完成 ${staff.openCount} 单）`"
              :value="staff.id"
            >
              <div class="staff-option">
                <span>{{ staff.username }}</span>
                <span class="staff-faults">{{ staff.qualified_faults.join('、') }} · 未完成 {{ staff.openCount }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="转派说明">
          <el-input v-model="transferForm.note" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="warning" :loading="acting" @click="confirmTransfer">确认转派</el-button>
      </template>
    </el-dialog>

    <TicketLogsDialog v-model="logsVisible" :logs="activeLogs" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  acceptTicket,
  completeTicket,
  listDeskTickets,
  listStaff,
  transferTicket,
} from '../api/repair';
import { useAuth } from '../stores/auth';
import { FAULT_TYPES, formatDateTime, statusTagType } from '../constants/repair';
import type { RepairTicket, StaffMember, TicketLog } from '../types/domain';
import TicketLogsDialog from '../components/TicketLogsDialog.vue';

const { user, logout: authLogout } = useAuth();
const router = useRouter();

const tickets = ref<RepairTicket[]>([]);
const staffList = ref<StaffMember[]>([]);
const loading = ref(false);
const acting = ref(false);
const statusFilter = ref('open');
const faultFilter = ref('');

const logsVisible = ref(false);
const activeLogs = ref<TicketLog[]>([]);

const transferVisible = ref(false);
const transferTarget = ref<RepairTicket | null>(null);
const transferForm = reactive({ assigneeId: undefined as number | undefined, note: '' });

// 只允许转给具备该工单故障资质的其他物业人员
const eligibleStaff = computed(() => {
  if (!transferTarget.value) return [];
  return staffList.value.filter(
    (staff) =>
      staff.qualified_faults.includes(transferTarget.value!.faultType) &&
      staff.id !== transferTarget.value!.assigneeId,
  );
});

onMounted(async () => {
  await Promise.all([loadTickets(), loadStaffList()]);
});

async function loadTickets() {
  loading.value = true;
  try {
    tickets.value = await listDeskTickets({
      status: statusFilter.value,
      faultType: faultFilter.value || undefined,
    });
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '工单加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadStaffList() {
  try {
    staffList.value = await listStaff();
  } catch {
    // 转派弹窗拉不到名册时给出提示即可
  }
}

async function handleAccept(row: RepairTicket) {
  try {
    let visitAt: string | undefined;
    try {
      const answer = await ElMessageBox.prompt('请设置预计上门时间（留空默认 24 小时内）', '接单', {
        confirmButtonText: '确认接单',
        cancelButtonText: '取消',
        inputPlaceholder: '格式：2026-09-21 14:30（可留空）',
        inputValue: '',
      });
      if (answer.value?.trim()) {
        visitAt = answer.value.trim().replace(' ', 'T');
      }
    } catch {
      return; // 取消接单
    }
    acting.value = true;
    const updated = await acceptTicket(row.id, row.version, visitAt);
    ElMessage.success(`接单成功，预计上门 ${formatDateTime(updated.estimatedVisitAt)}`);
    await Promise.all([loadTickets(), loadStaffList()]);
  } catch (err) {
    await loadTickets(); // 刷新后与接口一致
    ElMessage.error(err instanceof Error ? err.message : '接单失败');
  } finally {
    acting.value = false;
  }
}

function openTransfer(row: RepairTicket) {
  transferTarget.value = row;
  transferForm.assigneeId = undefined;
  transferForm.note = '';
  transferVisible.value = true;
}

async function confirmTransfer() {
  if (!transferTarget.value || !transferForm.assigneeId) {
    ElMessage.warning('请选择转派目标');
    return;
  }
  acting.value = true;
  try {
    await transferTicket(
      transferTarget.value.id,
      transferTarget.value.version,
      transferForm.assigneeId,
      transferForm.note,
    );
    ElMessage.success('工单已转派');
    transferVisible.value = false;
    await Promise.all([loadTickets(), loadStaffList()]);
  } catch (err) {
    await loadTickets();
    ElMessage.error(err instanceof Error ? err.message : '转派失败');
  } finally {
    acting.value = false;
  }
}

async function handleComplete(row: RepairTicket) {
  try {
    const answer = await ElMessageBox.prompt('完工备注（可留空）', '完工确认', {
      confirmButtonText: '确认完工',
      cancelButtonText: '取消',
      inputValue: '',
    });
    acting.value = true;
    await completeTicket(row.id, row.version, answer.value ?? '');
    ElMessage.success('工单已完工');
    await loadTickets();
  } catch (err) {
    if (err === 'cancel' || err?.toString?.().includes('cancel')) return;
    await loadTickets();
    ElMessage.error(err instanceof Error ? err.message : '完工失败');
  } finally {
    acting.value = false;
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

.qual-tag { margin-left: 4px; }
.sub { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.reporter { color: #8a93a5; font-size: 12px; }
.version { font-size: 11px; color: #a5adba; margin-top: 2px; }
.staff-option { display: flex; justify-content: space-between; width: 100%; }
.staff-faults { color: #8a93a5; font-size: 12px; }
</style>
