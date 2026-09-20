import { reactive } from 'vue';
import { getToken, login, setToken } from '../api/client';
import type { User } from '../types/domain';

export const session = reactive({
  user: null as User | null,
  get loggedIn(): boolean {
    return this.user !== null;
  },
});

export async function loginAs(phone: string) {
  const result = await login(phone);
  setToken(result.token);
  session.user = result.user;
}

export function restoreSession(): boolean {
  return Boolean(getToken());
}
