<template>
  <main class="page">
    <section class="toolbar">
      <div>
        <h1>RentFind 租房平台</h1>
        <p>房源搜索、预约看房、合同管理和物业报修集中处理。</p>
      </div>
      <el-segmented v-model="mode" :options="['列表视图', '地图视图']" />
    </section>

    <section class="filters">
      <el-input v-model="region" placeholder="区域" />
      <el-input-number v-model="maxRent" :min="1000" :step="500" />
      <el-select v-model="layout" placeholder="户型">
        <el-option label="全部" value="全部" />
        <el-option label="一室一厅" value="一室一厅" />
        <el-option label="两室一厅" value="两室一厅" />
        <el-option label="三室两厅" value="三室两厅" />
      </el-select>
    </section>

    <section v-if="mode === '地图视图'" class="map-panel">高德地图区域：按经纬度展示房源点位，当前示例加载 {{ filtered.length }} 套房源。</section>
    <section class="grid">
      <PropertyCard v-for="item in filtered" :key="item.id" :item="item" />
    </section>

    <RepairCenter v-if="session.user?.role === '租客'" />
    <StaffConsole v-else-if="session.user?.role === '物业人员'" />
    <section v-else class="panel">
      <p class="hint">切换到租客账号可提交报修，切换到物业账号可处理工单。</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import PropertyCard from '../components/PropertyCard.vue';
import RepairCenter from '../components/RepairCenter.vue';
import StaffConsole from '../components/StaffConsole.vue';
import { getProperties } from '../api/client';
import { session } from '../store/session';
import type { PropertyItem } from '../types/domain';

const properties = ref<PropertyItem[]>([]);
const mode = ref('列表视图');
const region = ref('');
const maxRent = ref(7000);
const layout = ref('全部');

onMounted(async () => {
  properties.value = await getProperties();
});

const filtered = computed(() => properties.value.filter((item) => {
  const hitRegion = !region.value || item.region.includes(region.value);
  const hitRent = item.rent <= maxRent.value;
  const hitLayout = layout.value === '全部' || item.layout === layout.value;
  return hitRegion && hitRent && hitLayout;
}));
</script>
