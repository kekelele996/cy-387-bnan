import datetime

from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from app.apps.contract.models import Contract
from app.apps.users.models import User
from app.constants.enums import (
    ACTION_ACCEPT,
    ACTION_COMPLETE,
    ACTION_CREATE,
    ACTION_DISPATCH,
    ACTION_MERGE,
    ACTION_REASSIGN,
    REPAIR_OPEN_STATUS,
    REPAIR_TYPES,
    ROLE_STAFF,
    STATUS_DONE,
    STATUS_PENDING,
    STATUS_PROCESSING,
)
from app.constants.errors import BizError

from .models import RepairTicket, RepairTicketLog

# 每积压一单，预计上门时间顺延的小时数
VISIT_HOURS_PER_TICKET = 2


def _unfinished_counts() -> dict:
    """统计每位物业人员名下未完成工单数。"""
    rows = (
        RepairTicket.objects.filter(status__in=REPAIR_OPEN_STATUS, assignee_id__isnull=False)
        .values('assignee_id')
        .annotate(total=Count('id'))
    )
    return {row['assignee_id']: row['total'] for row in rows}


def _qualified_staff(fault_type: str):
    """按故障类型匹配具备对应资质的物业人员。"""
    return [u for u in User.objects.filter(role=ROLE_STAFF).order_by('id') if fault_type in (u.qualifications or [])]


def pick_assignee(fault_type: str):
    """在具备资质的人员中挑选未完成工单数最少者。"""
    candidates = _qualified_staff(fault_type)
    if not candidates:
        return None
    counts = _unfinished_counts()
    return min(candidates, key=lambda u: (counts.get(u.id, 0), u.id))


def _expected_visit_time(staff_id: int):
    """按接单人当前积压量估算预计上门时间。"""
    queue = _unfinished_counts().get(staff_id, 0)
    return timezone.now() + datetime.timedelta(hours=VISIT_HOURS_PER_TICKET * max(queue, 1))


def _log(ticket, action, operator, from_status, to_status, note=''):
    RepairTicketLog.objects.create(
        ticket=ticket, action=action, operator=operator,
        from_status=from_status, to_status=to_status, note=note,
    )


def _get_ticket(ticket_id: int) -> RepairTicket:
    ticket = RepairTicket.objects.filter(pk=ticket_id).first()
    if ticket is None:
        raise BizError('TICKET_NOT_FOUND', '工单不存在', 404)
    return ticket


def _require_qualified(staff: User, fault_type: str):
    if fault_type not in (staff.qualifications or []):
        raise BizError('STAFF_UNQUALIFIED', f'不具备「{fault_type}」故障的处理资质', 403)


def create_ticket(*, tenant: User, property_obj, fault_type: str, description: str, photos: list):
    """住户报修：校验有效租约，未关闭同类型工单合并，否则建单并自动派单。

    全程单事务，任一步失败全部回滚。返回 (工单, 是否合并)。
    """
    if fault_type not in REPAIR_TYPES:
        raise BizError('REPAIR_INVALID', f'故障类型「{fault_type}」无效')
    if Contract.active_lease(tenant.id, property_obj.id) is None:
        raise BizError('LEASE_INVALID', '名下无该房屋的有效租约，无法报修')

    with transaction.atomic():
        existing = (
            RepairTicket.objects.select_for_update()
            .filter(property=property_obj, fault_type=fault_type, status__in=REPAIR_OPEN_STATUS)
            .order_by('id')
            .first()
        )
        if existing is not None:
            existing.description = f'{existing.description}\n【住户补充】{description}'
            existing.photos = [*(existing.photos or []), *photos]
            existing.version = F('version') + 1
            existing.save(update_fields=['description', 'photos', 'version', 'updated_at'])
            _log(existing, ACTION_MERGE, tenant, existing.status, existing.status, '同房屋同类型故障未关闭，合并到原工单')
            existing.refresh_from_db()
            return existing, True

        ticket = RepairTicket.objects.create(
            property=property_obj, tenant=tenant, fault_type=fault_type,
            description=description, photos=photos,
        )
        _log(ticket, ACTION_CREATE, tenant, '', STATUS_PENDING, '住户提交报修')

        staff = pick_assignee(fault_type)
        if staff is not None:
            RepairTicket.objects.filter(pk=ticket.pk, status=STATUS_PENDING).update(
                status=STATUS_PROCESSING, assignee_id=staff.id, version=F('version') + 1,
            )
            RepairTicket.objects.filter(pk=ticket.pk).update(expected_visit_at=_expected_visit_time(staff.id))
            _log(ticket, ACTION_DISPATCH, None, STATUS_PENDING, STATUS_PROCESSING, f'系统按资质与工单量派单给 {staff.name}')
            ticket.refresh_from_db()
        return ticket, False


def accept_ticket(*, staff: User, ticket_id: int) -> RepairTicket:
    """物业人员接单：仅待接单工单可接，并发下只有一人成功。"""
    ticket = _get_ticket(ticket_id)
    _require_qualified(staff, ticket.fault_type)

    with transaction.atomic():
        updated = RepairTicket.objects.filter(pk=ticket_id, status=STATUS_PENDING, assignee_id__isnull=True).update(
            status=STATUS_PROCESSING, assignee_id=staff.id, version=F('version') + 1, updated_at=timezone.now(),
        )
        if updated != 1:
            raise BizError('TICKET_STATE_CONFLICT', '工单已被接单或状态已变化，请刷新', 409)
        RepairTicket.objects.filter(pk=ticket_id).update(expected_visit_at=_expected_visit_time(staff.id))
        _log(ticket, ACTION_ACCEPT, staff, STATUS_PENDING, STATUS_PROCESSING, '物业人员接单')
        ticket.refresh_from_db()
    return ticket


def reassign_ticket(*, operator: User, ticket_id: int, target_staff_id: int, note: str = '') -> RepairTicket:
    """转派：仅当前责任人可操作，接收人必须具备对应资质。"""
    ticket = _get_ticket(ticket_id)
    _require_responsible(ticket, operator)
    target = User.objects.filter(pk=target_staff_id, role=ROLE_STAFF).first()
    if target is None:
        raise BizError('STAFF_NOT_FOUND', '目标物业人员不存在', 404)
    _require_qualified(target, ticket.fault_type)
    if target.id == operator.id:
        raise BizError('REPAIR_INVALID', '不能转派给自己')

    with transaction.atomic():
        updated = RepairTicket.objects.filter(
            pk=ticket_id, status=STATUS_PROCESSING, assignee_id=operator.id,
        ).update(assignee_id=target.id, version=F('version') + 1, updated_at=timezone.now())
        if updated != 1:
            _raise_state_error(ticket_id, operator)
        RepairTicket.objects.filter(pk=ticket_id).update(expected_visit_at=_expected_visit_time(target.id))
        _log(ticket, ACTION_REASSIGN, operator, STATUS_PROCESSING, STATUS_PROCESSING, note or f'转派给 {target.name}')
        ticket.refresh_from_db()
    return ticket


def complete_ticket(*, operator: User, ticket_id: int, note: str = '') -> RepairTicket:
    """完工：仅当前责任人可操作，已完工工单拒绝重复操作。"""
    ticket = _get_ticket(ticket_id)
    _require_responsible(ticket, operator)

    with transaction.atomic():
        updated = RepairTicket.objects.filter(
            pk=ticket_id, status=STATUS_PROCESSING, assignee_id=operator.id,
        ).update(status=STATUS_DONE, completed_at=timezone.now(), version=F('version') + 1, updated_at=timezone.now())
        if updated != 1:
            _raise_state_error(ticket_id, operator)
        _log(ticket, ACTION_COMPLETE, operator, STATUS_PROCESSING, STATUS_DONE, note or '维修完成')
        ticket.refresh_from_db()
    return ticket


def _require_responsible(ticket: RepairTicket, operator: User):
    """前置校验当前责任人与状态，并发场景仍由条件更新兜底。"""
    if ticket.status == STATUS_DONE:
        raise BizError('TICKET_STATE_CONFLICT', '工单已完工，无法重复操作', 409)
    if ticket.status != STATUS_PROCESSING or ticket.assignee_id != operator.id:
        raise BizError('TICKET_FORBIDDEN', '仅当前责任人可执行该操作', 403)


def _raise_state_error(ticket_id: int, operator: User):
    """条件更新未命中时，区分是状态问题还是责任人问题。"""
    current = RepairTicket.objects.filter(pk=ticket_id).first()
    if current is None:
        raise BizError('TICKET_NOT_FOUND', '工单不存在', 404)
    if current.status == STATUS_DONE:
        raise BizError('TICKET_STATE_CONFLICT', '工单已完工，无法重复操作', 409)
    if current.assignee_id != operator.id:
        raise BizError('TICKET_FORBIDDEN', '仅当前责任人可执行该操作', 403)
    raise BizError('TICKET_STATE_CONFLICT', '工单状态已变化，请刷新', 409)
