from django.contrib.auth.models import AbstractUser
from django.db import models

from app.constants.enums import ROLE_RESIDENT, ROLE_CHOICES


class User(AbstractUser):
    """平台用户：房东 / 租客 / 物业人员。"""

    role = models.CharField('角色', max_length=16, choices=ROLE_CHOICES, default=ROLE_RESIDENT)
    phone = models.CharField('联系电话', max_length=20, blank=True)
    # 物业人员具备资质的故障类型列表，如 ["水电", "门锁"]
    qualified_faults = models.JSONField('可处理故障类型', default=list, blank=True)

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return f'{self.username}（{self.role}）'

    @property
    def is_staff_member(self):
        from app.constants.enums import ROLE_STAFF

        return self.role == ROLE_STAFF

    @property
    def is_resident(self):
        return self.role == ROLE_RESIDENT
