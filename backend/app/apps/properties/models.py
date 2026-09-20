from django.db import models
from django.utils import timezone

from app.constants.enums import HOUSE_STATUS_CHOICES, LEASE_ACTIVE, LEASE_STATUS_CHOICES
from app.apps.users.models import User


class House(models.Model):
    """出租房屋。"""

    community = models.CharField('小区名称', max_length=80)
    region = models.CharField('所在区域', max_length=40)
    layout = models.CharField('户型', max_length=20)
    area = models.IntegerField('面积(㎡)')
    rent = models.IntegerField('月租金')
    deposit = models.IntegerField('押金')
    payment = models.CharField('付款方式', max_length=20)
    facilities = models.JSONField('配套设施', default=list, blank=True)
    status = models.CharField('房屋状态', max_length=20, choices=HOUSE_STATUS_CHOICES, default='待出租')
    landlord_phone = models.CharField('房东电话', max_length=30, blank=True)

    class Meta:
        verbose_name = '房屋'
        verbose_name_plural = '房屋'
        ordering = ['id']

    def __str__(self):
        return f'{self.community}-{self.layout}'


class Lease(models.Model):
    """租赁合同：决定住户能否为某房屋报修。"""

    house = models.ForeignKey(House, verbose_name='房屋', related_name='leases', on_delete=models.CASCADE)
    tenant = models.ForeignKey(User, verbose_name='租客', related_name='leases', on_delete=models.CASCADE)
    start_date = models.DateField('租期开始')
    end_date = models.DateField('租期结束')
    status = models.CharField('租约状态', max_length=16, choices=LEASE_STATUS_CHOICES, default=LEASE_ACTIVE)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '租约'
        verbose_name_plural = '租约'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.tenant_id}-{self.house_id}-{self.status}'

    @property
    def is_active(self):
        today = timezone.localdate()
        return self.status == LEASE_ACTIVE and self.start_date <= today <= self.end_date
