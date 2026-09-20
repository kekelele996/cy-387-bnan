<template>
  <div>
    <header class="topbar">
      <span class="brand">RentFind</span>
      <div class="account">
        <el-tag v-if="session.user" size="small">{{ session.user.role }}</el-tag>
        <el-select
          :model-value="session.user?.phone"
          size="small"
          placeholder="选择演示账号"
          class="account-select"
          @change="switchUser"
        >
          <el-option
            v-for="user in users"
            :key="user.id"
            :label="`${user.name}（${user.role}）`"
            :value="user.phone"
          />
        </el-select>
      </div>
    </header>
    <HomeView />
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { onMounted, ref } from 'vue';
import { getUsers } from './api/client';
import { loginAs, session } from './store/session';
import type { User } from './types/domain';
import HomeView from './views/HomeView.vue';

const users = ref<User[]>([]);

onMounted(async () => {
  users.value = await getUsers();
  const firstTenant = users.value.find((user) => user.role === '租客') || users.value[0];
  if (firstTenant) await switchUser(firstTenant.phone);
});

async function switchUser(phone: string) {
  try {
    await loginAs(phone);
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}
</script>
