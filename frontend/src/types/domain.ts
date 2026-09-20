export interface UserInfo {
  id: number;
  username: string;
  role: string;
  phone: string;
  qualified_faults: string[];
}

export interface HouseItem {
  id: number;
  community: string;
  region: string;
  layout: string;
  area: number;
  rent: number;
  deposit: number;
  payment: string;
  facilities: string[];
  status: string;
  landlordPhone: string;
}

export interface TicketLog {
  id: number;
  action: string;
  operatorName: string;
  from_status: string;
  to_status: string;
  note: string;
  created_at: string;
}

export interface RepairTicket {
  id: number;
  houseId: number;
  houseLabel: string;
  reporterName: string;
  faultType: string;
  description: string;
  photo: string | null;
  status: string;
  assigneeId: number | null;
  assigneeName: string | null;
  estimatedVisitAt: string | null;
  completedAt: string | null;
  version: number;
  createdAt: string;
  logs: TicketLog[];
  merged?: boolean;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  error: { code: string; message: string; details?: unknown } | null;
}

export interface StaffMember {
  id: number;
  username: string;
  qualified_faults: string[];
  openCount: number;
}
