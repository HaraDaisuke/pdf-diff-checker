<template>
  <v-app-bar color="primary" density="compact">
    <v-app-bar-nav-icon @click="$emit('toggle-drawer')"></v-app-bar-nav-icon>
    <v-app-bar-title>PDF Diff Checker</v-app-bar-title>
  </v-app-bar>
</template>

<script setup>
defineEmits(['toggle-drawer']);
</script>
