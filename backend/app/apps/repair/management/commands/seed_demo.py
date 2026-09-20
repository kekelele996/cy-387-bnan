"""生成报修闭环演示数据：

- 住户 zhangsan 对“海棠公寓 2-1-301”持有生效租约；
- 住户 lisi 对“梧桐里 1-2-502”的租约已到期（用于无有效租约被拒场景）；
- 四名物业人员分别具备不同故障资质。
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.apps.properties.models import House, Lease
from app.apps.users.models import User
from app.constants.enums import (
    FAULT_APPLIANCE,
    FAULT_LOCK,
    FAULT_PIPE,
    FAULT_PLUMBING_ELECTRIC,
    LEASE_ACTIVE,
    LEASE_EXPIRED,
    ROLE_RESIDENT,
    ROLE_STAFF,
)


class Command(BaseCommand):
    help = '创建报修闭环演示数据'

    def handle(self, *args, **options):
        today = timezone.localdate()

        zhangsan, _ = User.objects.get_or_create(
            username='zhangsan', defaults={'role': ROLE_RESIDENT, 'phone': '13900000001'}
        )
        zhangsan.set_password('demo1234')
        zhangsan.role = ROLE_RESIDENT
        zhangsan.save()

        lisi, _ = User.objects.get_or_create(
            username='lisi', defaults={'role': ROLE_RESIDENT, 'phone': '13900000002'}
        )
        lisi.set_password('demo1234')
        lisi.role = ROLE_RESIDENT
        lisi.save()

        staff_specs = [
            ('shui', '水电王师傅', [FAULT_PLUMBING_ELECTRIC]),
            ('suo', '门锁李师傅', [FAULT_LOCK]),
            ('guan', '管道赵师傅', [FAULT_PIPE]),
            ('jia', '家电全能陈师傅', [FAULT_APPLIANCE, FAULT_PLUMBING_ELECTRIC]),
        ]
        for username, phone, faults in staff_specs:
            staff, _ = User.objects.get_or_create(username=username, defaults={'role': ROLE_STAFF})
            staff.set_password('demo1234')
            staff.role = ROLE_STAFF
            staff.qualified_faults = faults
            staff.save()

        house1, _ = House.objects.get_or_create(
            id=1,
            defaults={
                'community': '海棠公寓', 'region': '滨江区', 'layout': '两室一厅',
                'area': 76, 'rent': 5200, 'deposit': 5200, 'payment': '月付',
                'facilities': ['空调', '洗衣机', '宽带'], 'landlord_phone': '13800000001',
            },
        )
        house2, _ = House.objects.get_or_create(
            id=2,
            defaults={
                'community': '梧桐里', 'region': '西湖区', 'layout': '一室一厅',
                'area': 48, 'rent': 3900, 'deposit': 3900, 'payment': '季付',
                'facilities': ['冰箱', '宽带'], 'landlord_phone': '13800000002',
            },
        )

        Lease.objects.get_or_create(
            house=house1, tenant=zhangsan,
            defaults={
                'status': LEASE_ACTIVE,
                'start_date': today - timedelta(days=30),
                'end_date': today + timedelta(days=335),
            },
        )
        Lease.objects.get_or_create(
            house=house2, tenant=lisi,
            defaults={
                'status': LEASE_EXPIRED,
                'start_date': today - timedelta(days=400),
                'end_date': today - timedelta(days=35),
            },
        )

        self.stdout.write(self.style.SUCCESS('演示数据创建完成'))
        self.stdout.write('住户: zhangsan / demo1234（海棠公寓有效租约）')
        self.stdout.write('住户: lisi / demo1234（梧桐里租约已到期）')
        self.stdout.write('物业: shui|suo|guan|jia / demo1234')
