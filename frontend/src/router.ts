import { createRouter, createWebHistory } from 'vue-router';
import { getToken } from './api/client';
import LoginView from './views/LoginView.vue';
import ResidentView from './views/ResidentView.vue';
import StaffView from './views/StaffView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/resident', name: 'resident', component: ResidentView, meta: { role: '租客' } },
    { path: '/staff', name: 'staff', component: StaffView, meta: { role: '物业人员' } },
    { path: '/:pathMatch(.*)*', redirect: '/login' },
  ],
});

router.beforeEach((to) => {
  const token = getToken();
  if (to.name !== 'login' && !token) return { name: 'login' };
  if (to.name === 'login' && token) return { name: roleHome() };
  return true;
});

function roleHome() {
  try {
    const raw = localStorage.getItem('rentfind_user');
    const user = raw ? JSON.parse(raw) : null;
    return user?.role === '物业人员' ? 'staff' : 'resident';
  } catch {
    return 'resident';
  }
}

export default router;
