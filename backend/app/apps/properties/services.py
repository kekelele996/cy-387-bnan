"""租约领域服务：住户与房屋的有效租约关系。"""

from django.utils import timezone

from .models import Lease
from app.constants.enums import LEASE_ACTIVE


def get_active_lease(tenant, house):
    """返回住户在某房屋名下当前有效的租约；不存在返回 None。"""
    today = timezone.localdate()
    return (
        Lease.objects.filter(
            tenant=tenant,
            house=house,
            status=LEASE_ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .select_related('house')
        .first()
    )
