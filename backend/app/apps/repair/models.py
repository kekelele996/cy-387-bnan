from django.db import models

from app.constants.enums import REPAIR_ACTIONS, REPAIR_STATUS, REPAIR_TYPES, STATUS_PENDING


class RepairTicket(models.Model):
    """物业报修工单。"""

    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='repair_tickets')
    tenant = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='repair_tickets')
    fault_type = models.CharField(max_length=20, choices=[(t, t) for t in REPAIR_TYPES])
    description = models.TextField()
    photos = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=[(s, s) for s in REPAIR_STATUS], default=STATUS_PENDING)
    assignee = models.ForeignKey('users.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tickets')
    expected_visit_at = models.DateTimeField(null=True, blank=True, help_text='预计上门时间')
    version = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'工单#{self.pk} {self.fault_type} {self.status}'


class RepairTicketLog(models.Model):
    """工单处理轨迹，每次状态变化留痕。"""

    ticket = models.ForeignKey(RepairTicket, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=10, choices=[(a, a) for a in REPAIR_ACTIONS])
    operator = models.ForeignKey('users.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='repair_logs')
    from_status = models.CharField(max_length=20, blank=True, default='')
    to_status = models.CharField(max_length=20, blank=True, default='')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
