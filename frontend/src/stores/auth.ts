import { computed, ref } from 'vue';
import { clearSession, getStoredUser } from '../api/client';
import type { UserInfo } from '../types/domain';

const user = ref<UserInfo | null>(getStoredUser());

export function useAuth() {
  const isLoggedIn = computed(() => user.value !== null);
  const role = computed(() => user.value?.role ?? '');

  function setUser(next: UserInfo) {
    user.value = next;
  }

  function logout() {
    clearSession();
    user.value = null;
  }

  return { user, isLoggedIn, role, setUser, logout };
}
