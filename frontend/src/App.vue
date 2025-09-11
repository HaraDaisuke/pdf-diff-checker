<template>
  <v-app>
    <AppHeader @toggle-drawer="drawer = !drawer" />

    <v-navigation-drawer v-model="drawer" temporary>
      <v-list nav>
        <v-list-item
          v-for="item in menuItems"
          :key="item.title"
          :to="item.to"
          link
        >
          <template v-slot:prepend>
            <v-icon>{{ item.icon }}</v-icon>
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <router-view />
    </v-main>

    <AppFooter />
  </v-app>
</template>

<script setup>
import { ref } from 'vue';
import AppHeader from '@/components/AppHeader.vue';
import AppFooter from '@/components/AppFooter.vue';

const drawer = ref(null);

const menuItems = [
  { title: '全体比較', icon: 'mdi-select-compare', to: '/global-comparison' },
  { title: '部分比較', icon: 'mdi-vector-square', to: '/part-comparison' },
];
</script>