import { request, saveSession } from './client';
import type { RepairTicket, StaffMember, UserInfo } from '../types/domain';

export interface LoginResult {
  token: string;
  refresh: string;
  user: UserInfo;
}

export async function login(username: string, password: string): Promise<LoginResult> {
  const result = await request<LoginResult>('/auth/login/', {
    method: 'POST',
    body: { username, password },
  });
  saveSession(result.token, result.user);
  return result;
}

export async function register(payload: {
  username: string;
  password: string;
  role: string;
  phone?: string;
  qualified_faults?: string[];
}): Promise<UserInfo> {
  return request<UserInfo>('/auth/register/', { method: 'POST', body: payload });
}

export async function listMyTickets(): Promise<RepairTicket[]> {
  return request<RepairTicket[]>('/repairs/');
}

export async function listDeskTickets(params: { status?: string; faultType?: string } = {}): Promise<RepairTicket[]> {
  const search = new URLSearchParams();
  if (params.status) search.set('status', params.status);
  if (params.faultType) search.set('faultType', params.faultType);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<RepairTicket[]>(`/repairs/desk/${suffix}`);
}

export async function createRepair(payload: {
  houseId: number;
  faultType: string;
  description: string;
  photo?: File | null;
}): Promise<RepairTicket> {
  if (payload.photo) {
    const form = new FormData();
    form.append('houseId', String(payload.houseId));
    form.append('faultType', payload.faultType);
    form.append('description', payload.description);
    form.append('photo', payload.photo);
    return request<RepairTicket>('/repairs/', { method: 'POST', formData: form });
  }
  return request<RepairTicket>('/repairs/', {
    method: 'POST',
    body: { houseId: payload.houseId, faultType: payload.faultType, description: payload.description },
  });
}

export async function acceptTicket(
  ticketId: number,
  version: number,
  estimatedVisitAt?: string,
): Promise<RepairTicket> {
  return request<RepairTicket>(`/repairs/${ticketId}/accept/`, {
    method: 'POST',
    body: { version, estimatedVisitAt: estimatedVisitAt ?? null },
  });
}

export async function transferTicket(
  ticketId: number,
  version: number,
  assigneeId: number,
  note: string,
): Promise<RepairTicket> {
  return request<RepairTicket>(`/repairs/${ticketId}/transfer/`, {
    method: 'POST',
    body: { version, assigneeId, note },
  });
}

export async function completeTicket(ticketId: number, version: number, note = ''): Promise<RepairTicket> {
  return request<RepairTicket>(`/repairs/${ticketId}/complete/`, {
    method: 'POST',
    body: { version, note },
  });
}

export async function listStaff(): Promise<StaffMember[]> {
  return request<StaffMember[]>('/auth/staff/');
}
