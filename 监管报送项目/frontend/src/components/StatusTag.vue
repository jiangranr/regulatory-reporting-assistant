<template>
  <span :class="['tag', tone]"><slot /></span>
</template>

<script setup lang="ts">
defineProps<{
  tone: "orange" | "red" | "green" | "amber" | "blue" | "gray";
}>();
</script>
