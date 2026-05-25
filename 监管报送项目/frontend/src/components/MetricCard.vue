<template>
  <div :class="['metric-card', { warning }]">
    <div class="metric-icon">
      <component :is="iconComponent" />
    </div>
    <div class="metric-main">
      <div class="metric-label">{{ label }}</div>
      <div class="metric-row">
        <div class="metric-value">{{ value }}</div>
        <div class="metric-note">{{ note }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ClipboardCheck, FileText, Layers, ListTodo } from "lucide-vue-next";

const props = defineProps<{
  label: string;
  value: string | number;
  note: string;
  icon?: "task" | "document" | "rule" | "review";
  warning?: boolean;
}>();

const iconComponent = computed(() => {
  const icons = {
    task: ListTodo,
    document: FileText,
    rule: Layers,
    review: ClipboardCheck,
  };
  return icons[props.icon || "task"];
});
</script>
