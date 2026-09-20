export const FAULT_TYPES = ['水电', '门锁', '管道', '家电', '其他'] as const;

export const TICKET_STATUS = ['待受理', '处理中', '已完成'] as const;

const STATUS_TAG_TYPE: Record<string, string> = {
  待受理: 'warning',
  处理中: 'primary',
  已完成: 'success',
};

export function statusTagType(status: string): string {
  return STATUS_TAG_TYPE[status] ?? 'info';
}

export function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
