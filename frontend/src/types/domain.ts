export interface PropertyItem {
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

export interface User {
  id: number;
  name: string;
  phone: string;
  role: string;
  qualifications: string[];
}

export interface Contract {
  id: number;
  propertyId: number;
  community: string;
  layout: string;
  region: string;
  tenantName: string;
  landlordName: string;
  rent: number;
  startDate: string;
  endDate: string;
  status: string;
}

export interface RepairLog {
  id: number;
  action: string;
  operatorName: string;
  fromStatus: string;
  toStatus: string;
  note: string;
  createdAt: string;
}

export interface RepairTicket {
  id: number;
  propertyId: number;
  community: string;
  faultType: string;
  description: string;
  photos: string[];
  status: string;
  tenantName: string;
  assigneeId: number | null;
  assigneeName: string;
  expectedVisitAt: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  logs: RepairLog[];
  merged?: boolean;
}

export interface StaffOption {
  id: number;
  name: string;
  qualifications: string[];
  unfinishedCount: number;
}
