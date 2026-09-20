"""报修工单与处理轨迹模型。"""

from django.db import models

from app.apps.users.models import User
from app.constants.enums import (
    ACTION_CHOICES,
    FAULT_TYPE_CHOICES,
    TICKET_PENDING,
    TICKET_STATUS_CHOICES,
)
from app.apps.properties.models import House


class RepairTicket(models.Model):
    """物业报修工单。"""

    house = models.ForeignKey(House, verbose_name='房屋', related_name='repair_tickets', on_delete=models.PROTECT)
    reporter = models.ForeignKey(User, verbose_name='报修人', related_name='reported_tickets', on_delete=models.PROTECT)
    fault_type = models.CharField('故障类型', max_length=16, choices=FAULT_TYPE_CHOICES)
    description = models.TextField('故障描述')
    photo = models.ImageField('故障照片', upload_to='repairs/%Y%m%d/', blank=True, null=True)

    status = models.CharField('工单状态', max_length=16, choices=TICKET_STATUS_CHOICES, default=TICKET_PENDING)
    assignee = models.ForeignKey(
        User, verbose_name='当前责任人', related_name='assigned_tickets',
        null=True, blank=True, on_delete=models.PROTECT,
    )
    estimated_visit_at = models.DateTimeField('预计上门时间', null=True, blank=True)
    completed_at = models.DateTimeField('完工时间', null=True, blank=True)

    # 乐观锁版本号：每次状态变化 +1，并发操作只有一次能成功
    version = models.PositiveIntegerField('版本号', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '报修工单'
        verbose_name_plural = '报修工单'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['house', 'fault_type', 'status']),
            models.Index(fields=['assignee', 'status']),
        ]
        constraints = [
            # 同一房屋同类型故障只允许存在一个未关闭工单，数据库层兜底并发
            models.UniqueConstraint(
                fields=['house', 'fault_type'],
                condition=models.Q(status__in=['待受理', '处理中']),
                name='uniq_open_ticket_per_house_fault',
            )
        ]

    def __str__(self):
        return f'工单#{self.id}-{self.fault_type}-{self.status}'


class TicketLog(models.Model):
    """工单状态变化轨迹，任何一次处理动作都留痕。"""

    ticket = models.ForeignKey(RepairTicket, verbose_name='工单', related_name='logs', on_delete=models.CASCADE)
    action = models.CharField('动作', max_length=16, choices=ACTION_CHOICES)
    operator = models.ForeignKey(User, verbose_name='操作人', related_name='ticket_logs', on_delete=models.PROTECT)
    from_status = models.CharField('变化前状态', max_length=16, blank=True, default='')
    to_status = models.CharField('变化后状态', max_length=16, blank=True, default='')
    note = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '工单处理轨迹'
        verbose_name_plural = '工单处理轨迹'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'工单#{self.ticket_id}-{self.action}'
