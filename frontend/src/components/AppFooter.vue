<template>
  <v-footer height="40">
    <div class="text-caption text-disabled">
      &copy; {{ new Date().getFullYear() }} [ここに会社名]
    </div>
    <v-spacer></v-spacer>
    <div class="text-caption text-disabled">
      バージョン 1.0.0
    </div>
    <v-spacer></v-spacer>
    <a
      class="text-decoration-none text-caption text-disabled"
      href="[社内ヘルプデスクのURL]"
      target="_blank"
    >
      ヘルプとサポート
    </a>
  </v-footer>
</template>

<script setup>
// No script needed for this simple footer
</script>

<style scoped>
a {
  transition: color .2s ease-in-out;
}
a:hover {
  color: rgba(var(--v-theme-primary), 1);
}
</style>