<template>
  <el-dialog v-model="visible" title="处理轨迹" width="560px">
    <TicketTimeline :logs="logs" />
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import type { TicketLog } from '../types/domain';
import TicketTimeline from './TicketTimeline.vue';

const props = defineProps<{ modelValue: boolean; logs: TicketLog[] }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const visible = ref(props.modelValue);
watch(() => props.modelValue, (v) => (visible.value = v));
watch(visible, (v) => emit('update:modelValue', v));
</script>
