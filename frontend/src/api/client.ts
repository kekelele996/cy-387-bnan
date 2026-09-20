import type { Contract, PropertyItem, RepairTicket, StaffOption, User } from '../types/domain';

const API_BASE = '/api';
const TOKEN_KEY = 'rentfind_token';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (body && body.message) message = body.message;
    } catch {
      // 保留默认提示
    }
    throw new Error(message);
  }
  return response.json();
}

export async function login(phone: string): Promise<{ token: string; user: User }> {
  return request('/auth/login/', { method: 'POST', body: JSON.stringify({ phone }) });
}

export async function getUsers(): Promise<User[]> {
  return request('/users/');
}

export async function getProperties(): Promise<PropertyItem[]> {
  return request('/properties/');
}

export async function getMyContracts(): Promise<Contract[]> {
  return request('/contracts/');
}

export async function getRepairs(): Promise<RepairTicket[]> {
  return request('/repairs/');
}

export async function createRepair(payload: {
  propertyId: number;
  faultType: string;
  description: string;
  photos: string[];
}): Promise<RepairTicket> {
  return request('/repairs/', { method: 'POST', body: JSON.stringify(payload) });
}

export async function acceptRepair(id: number): Promise<RepairTicket> {
  return request(`/repairs/${id}/accept/`, { method: 'POST', body: JSON.stringify({}) });
}

export async function reassignRepair(id: number, targetStaffId: number, note: string): Promise<RepairTicket> {
  return request(`/repairs/${id}/reassign/`, { method: 'POST', body: JSON.stringify({ targetStaffId, note }) });
}

export async function completeRepair(id: number, note: string): Promise<RepairTicket> {
  return request(`/repairs/${id}/complete/`, { method: 'POST', body: JSON.stringify({ note }) });
}

export async function getRepairStaff(): Promise<StaffOption[]> {
  return request('/repairs/staff/');
}
