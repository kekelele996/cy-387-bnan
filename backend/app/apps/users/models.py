from django.db import models

from app.constants.enums import ROLE_TENANT, USER_ROLES


class User(models.Model):
    """平台用户，角色区分房东、租客和物业人员。"""

    name = models.CharField(max_length=40)
    phone = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=20, choices=[(r, r) for r in USER_ROLES], default=ROLE_TENANT)
    qualifications = models.JSONField(default=list, blank=True, help_text='物业人员可处理的故障类型')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return f'{self.name}({self.role})'
