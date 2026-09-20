from django.db import models
from django.utils import timezone

from app.constants.enums import CONTRACT_ACTIVE, CONTRACT_STATUS


class Contract(models.Model):
    """租赁合同，记录租期、租金与双方信息。"""

    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='contracts')
    tenant = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='contracts')
    landlord_name = models.CharField(max_length=40)
    rent = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=[(s, s) for s in CONTRACT_STATUS], default=CONTRACT_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self, on_date=None) -> bool:
        """判断合同在指定日期是否有效。"""
        on_date = on_date or timezone.localdate()
        return self.status == CONTRACT_ACTIVE and self.start_date <= on_date <= self.end_date

    @classmethod
    def active_lease(cls, tenant_id: int, property_id: int):
        """查询住户对某房屋当前有效的租约。"""
        today = timezone.localdate()
        return cls.objects.filter(
            tenant_id=tenant_id,
            property_id=property_id,
            status=CONTRACT_ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        ).first()
