"""报修工单领域服务：合并、派单、转派、完工等状态流转全部在此完成。

约定：
- 每个状态流转都在单个数据库事务内完成，任一步失败全部回滚；
- 最终状态切换使用带状态/责任人/版本条件的 UPDATE，数据库层保证并发只有一次成功；
- 每次状态变化写一条 TicketLog 处理轨迹。
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from app.apps.properties.models import House
from app.apps.properties.services import get_active_lease
from app.apps.users.models import User
from app.constants.enums import (
    ACTION_ACCEPT,
    ACTION_COMPLETE,
    ACTION_CREATE,
    ACTION_TRANSFER,
    DEFAULT_VISIT_WITHIN_HOURS,
    OPEN_TICKET_STATUS,
    TICKET_COMPLETED,
    TICKET_PENDING,
    TICKET_PROCESSING,
)
from app.utils.exception_handler import BusinessError
from app.utils.logger import get_logger

from .models import RepairTicket, TicketLog

logger = get_logger('repair')


def _write_log(ticket, action, operator, from_status, to_status, note=''):
    return TicketLog.objects.create(
        ticket=ticket,
        action=action,
        operator=operator,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )


def _load_ticket(ticket_id):
    try:
        return RepairTicket.objects.select_related('house', 'reporter', 'assignee').get(pk=ticket_id)
    except RepairTicket.DoesNotExist:
        raise BusinessError('TICKET_NOT_FOUND')


def _guard_version(ticket, expected_version):
    """客户端携带过期版本号直接拒绝（物业台刷新前后状态一致性）。"""
    if expected_version is not None and ticket.version != expected_version:
        raise BusinessError('CONFLICT', '工单状态已变化，请刷新后重试')


def choose_least_loaded_staff(fault_type):
    """在具备该故障资质的物业人员中，挑选未完成工单数最少者（同负载取最早入职）。"""
    # 资质用 JSON 数组存储，SQLite 不支持 JSON contains 查询；物业人员规模小，在内存过滤
    qualified = [
        staff
        for staff in User.objects.filter(role='物业人员').order_by('id')
        if fault_type in (staff.qualified_faults or [])
    ]
    if not qualified:
        raise BusinessError('NO_QUALIFIED_STAFF')

    open_counts = dict(
        RepairTicket.objects.filter(assignee__in=qualified, status__in=OPEN_TICKET_STATUS)
        .values_list('assignee_id')
        .annotate(open_count=Count('id'))
    )
    chosen = min(qualified, key=lambda staff: (open_counts.get(staff.id, 0), staff.id))
    logger.info('派单匹配 fault=%s staff=%s open=%s', fault_type, chosen.id, open_counts.get(chosen.id, 0))
    return chosen


def _default_visit_time():
    return timezone.now() + timezone.timedelta(hours=DEFAULT_VISIT_WITHIN_HOURS)


def _validate_visit_time(estimated_visit_at):
    if estimated_visit_at is None:
        return _default_visit_time()
    parsed = parse_datetime(estimated_visit_at) if isinstance(estimated_visit_at, str) else estimated_visit_at
    if parsed is None:
        raise BusinessError('VISIT_TIME_INVALID')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    if parsed <= timezone.now():
        raise BusinessError('VISIT_TIME_INVALID')
    return parsed


def create_ticket(*, reporter, house_id, fault_type, description, photo=None):
    """住户提交报修；同一房屋同类型有未关闭工单时合并到原工单。

    返回 (工单, 是否合并)。
    """
    if not reporter.is_resident:
        raise BusinessError('FORBIDDEN', '只有住户可以提交报修')

    try:
        house = House.objects.get(pk=house_id)
    except House.DoesNotExist:
        raise BusinessError('HOUSE_NOT_FOUND')

    # 住户只能为名下有有效租约的房屋报修
    if get_active_lease(reporter, house) is None:
        logger.info('报修被拒：user=%s house=%s 无有效租约', reporter.id, house_id)
        raise BusinessError('NO_ACTIVE_LEASE')

    with transaction.atomic():
        existing = (
            RepairTicket.objects.filter(house=house, fault_type=fault_type, status__in=OPEN_TICKET_STATUS)
            .select_related('house', 'reporter')
            .first()
        )
        if existing is not None:
            _write_log(existing, ACTION_CREATE, reporter, existing.status, existing.status,
                       f'{reporter.username} 补充报修：{description}')
            existing.was_merged = True
            logger.info('报修合并到原工单 ticket=%s', existing.id)
            return existing, True

        ticket = RepairTicket(
            house=house,
            reporter=reporter,
            fault_type=fault_type,
            description=description,
            photo=photo,
            status=TICKET_PENDING,
        )
        try:
            # 内层 savepoint：并发下唯一索引拦截后回滚到保存点，外层事务仍可继续走合并分支
            with transaction.atomic():
                ticket.save()
        except IntegrityError:
            merged = (
                RepairTicket.objects.filter(house=house, fault_type=fault_type, status__in=OPEN_TICKET_STATUS)
                .select_related('house', 'reporter')
                .first()
            )
            if merged is None:
                raise
            _write_log(merged, ACTION_CREATE, reporter, merged.status, merged.status,
                       f'{reporter.username} 补充报修：{description}')
            merged.was_merged = True
            logger.info('并发报修合并 ticket=%s', merged.id)
            return merged, True

        _write_log(ticket, ACTION_CREATE, reporter, '', TICKET_PENDING, description)
        logger.info('新报修工单 ticket=%s house=%s fault=%s', ticket.id, house_id, fault_type)
        return ticket, False


def _fail_after_lost_update(ticket, *, completed_code, wrong_status_code, owner_required=False):
    """条件 UPDATE 未命中时，重新读取并给出准确的业务错误。"""
    fresh = RepairTicket.objects.filter(pk=ticket.id).first()
    if fresh is None:
        raise BusinessError('TICKET_NOT_FOUND')
    if fresh.status == TICKET_COMPLETED:
        raise BusinessError(completed_code)
    if owner_required and fresh.assignee_id != ticket.assignee_id:
        raise BusinessError('NOT_CURRENT_OWNER')
    if fresh.status != ticket.status:
        raise BusinessError(wrong_status_code)
    raise BusinessError('CONFLICT', '工单状态已变化，请刷新后重试')


def accept_ticket(*, staff, ticket_id, expected_version=None, estimated_visit_at=None):
    """物业人员接单：按资质 + 最少未完成工单自动匹配责任人。"""
    if not staff.is_staff_member:
        raise BusinessError('FORBIDDEN', '只有物业人员可以接单')

    visit_time = _validate_visit_time(estimated_visit_at)

    with transaction.atomic():
        ticket = _load_ticket(ticket_id)
        if ticket.status == TICKET_COMPLETED:
            raise BusinessError('TICKET_COMPLETED')
        if ticket.status != TICKET_PENDING:
            raise BusinessError('TICKET_NOT_PENDING')
        _guard_version(ticket, expected_version)

        # 操作者本人必须具备该故障类型资质
        if ticket.fault_type not in (staff.qualified_faults or []):
            raise BusinessError('STAFF_NOT_QUALIFIED', f'您不具备 {ticket.fault_type} 类故障的处理资质')

        # 自动匹配：合格资质中未完成工单数最少者
        chosen = choose_least_loaded_staff(ticket.fault_type)
        # 多物业并发抢单：只有系统判定为最低负载的责任人能成功
        if chosen.id != staff.id:
            raise BusinessError(
                'STAFF_NOT_QUALIFIED',
                f'该工单将分配给当前负载更低的物业人员 {chosen.username}',
            )

        # 始终用读取时的 version 做条件：并发重复/抢单时第二个 UPDATE 匹配 0 行
        updated = RepairTicket.objects.filter(
            pk=ticket_id, status=TICKET_PENDING, version=ticket.version
        ).update(
            status=TICKET_PROCESSING,
            assignee=chosen,
            estimated_visit_at=visit_time,
            version=F('version') + 1,
        )
        if not updated:
            _fail_after_lost_update(
                ticket, completed_code='TICKET_COMPLETED', wrong_status_code='TICKET_NOT_PENDING'
            )

        _write_log(
            ticket, ACTION_ACCEPT, staff, TICKET_PENDING, TICKET_PROCESSING,
            f'预计上门时间 {timezone.localtime(visit_time):%Y-%m-%d %H:%M}',
        )
        logger.info('工单接单 ticket=%s staff=%s visit=%s', ticket_id, staff.id, visit_time)
        return _load_ticket(ticket_id)


def transfer_ticket(*, staff, ticket_id, assignee_id, expected_version=None, note=''):
    """转派：校验当前责任人、工单状态和新责任人资质。"""
    with transaction.atomic():
        ticket = _load_ticket(ticket_id)
        if ticket.status == TICKET_COMPLETED:
            raise BusinessError('TICKET_COMPLETED')
        if ticket.status != TICKET_PROCESSING:
            raise BusinessError('TICKET_NOT_PROCESSING')
        _guard_version(ticket, expected_version)
        if ticket.assignee_id != staff.id:
            raise BusinessError('NOT_CURRENT_OWNER')

        try:
            target = User.objects.get(pk=assignee_id, role='物业人员')
        except User.DoesNotExist:
            raise BusinessError('STAFF_NOT_QUALIFIED', '目标物业人员不存在')
        if ticket.fault_type not in (target.qualified_faults or []):
            raise BusinessError('STAFF_NOT_QUALIFIED', f'{target.username} 不具备 {ticket.fault_type} 类故障资质')
        if target.id == staff.id:
            raise BusinessError('STAFF_NOT_QUALIFIED', '不能转派给自己')

        updated = RepairTicket.objects.filter(
            pk=ticket_id, status=TICKET_PROCESSING, assignee=staff, version=ticket.version
        ).update(assignee=target, version=F('version') + 1)
        if not updated:
            _fail_after_lost_update(
                ticket,
                completed_code='TICKET_COMPLETED',
                wrong_status_code='TICKET_NOT_PROCESSING',
                owner_required=True,
            )

        _write_log(
            ticket, ACTION_TRANSFER, staff, TICKET_PROCESSING, TICKET_PROCESSING,
            f'{staff.username} 转派给 {target.username}' + (f'：{note}' if note else ''),
        )
        logger.info('工单转派 ticket=%s from=%s to=%s', ticket_id, staff.id, target.id)
        return _load_ticket(ticket_id)


def complete_ticket(*, staff, ticket_id, expected_version=None, note=''):
    """完工：仅当前责任人、在处理中状态可操作。"""
    with transaction.atomic():
        ticket = _load_ticket(ticket_id)
        if ticket.status == TICKET_COMPLETED:
            raise BusinessError('TICKET_COMPLETED')
        if ticket.status != TICKET_PROCESSING:
            raise BusinessError('TICKET_NOT_PROCESSING')
        _guard_version(ticket, expected_version)
        if ticket.assignee_id != staff.id:
            raise BusinessError('NOT_CURRENT_OWNER')

        finished_at = timezone.now()
        updated = RepairTicket.objects.filter(
            pk=ticket_id, status=TICKET_PROCESSING, assignee=staff, version=ticket.version
        ).update(
            status=TICKET_COMPLETED,
            completed_at=finished_at,
            version=F('version') + 1,
        )
        if not updated:
            _fail_after_lost_update(
                ticket,
                completed_code='TICKET_COMPLETED',
                wrong_status_code='TICKET_NOT_PROCESSING',
                owner_required=True,
            )

        _write_log(ticket, ACTION_COMPLETE, staff, TICKET_PROCESSING, TICKET_COMPLETED, note)
        logger.info('工单完工 ticket=%s staff=%s', ticket_id, staff.id)
        return _load_ticket(ticket_id)
