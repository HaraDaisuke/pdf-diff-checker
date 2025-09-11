import { createRouter, createWebHistory } from 'vue-router';
import GlobalComparison from '@/pages/GlobalComparison.vue';
import PartComparison from '@/pages/PartComparison.vue';

const routes = [
  {
    path: '/',
    redirect: '/global-comparison',
  },
  {
    path: '/global-comparison',
    name: 'GlobalComparison',
    component: GlobalComparison,
  },
  {
    path: '/part-comparison',
    name: 'PartComparison',
    component: PartComparison,
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;