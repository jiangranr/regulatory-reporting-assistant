<template>
  <ReviewTicketView
    :workflow="workflow"
    :busy="busy"
    @back="$emit('back')"
    @finish="$emit('finish')"
    @generate="$emit('generate')"
  />
</template>

<script setup lang="ts">
import ReviewTicketView from "./ReviewTicketView.vue";
import type { TaskWorkflow } from "@/types/api";

defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

defineEmits<{ back: []; finish: []; generate: [] }>();
</script>
