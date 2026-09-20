import datetime

from django.core.management.base import BaseCommand

from app.apps.contract.models import Contract
from app.apps.properties.models import Property
from app.apps.users.models import User
from app.constants.enums import CONTRACT_ACTIVE, CONTRACT_EXPIRED, ROLE_LANDLORD, ROLE_STAFF, ROLE_TENANT

DEMO_USERS = [
    ('宋房东', '13800000001', ROLE_LANDLORD, []),
    ('陈晨', '13900000001', ROLE_TENANT, []),
    ('林小', '13900000002', ROLE_TENANT, []),
    ('张师傅', '13700000001', ROLE_STAFF, ['水电', '门锁']),
    ('王师傅', '13700000002', ROLE_STAFF, ['管道', '家电']),
    ('李师傅', '13700000003', ROLE_STAFF, ['水电', '管道', '家电', '门锁', '其他']),
]

DEMO_PROPERTIES = [
    ('海棠公寓', '滨江区', '两室一厅', 76, 5200, 5200, '月付', ['空调', '洗衣机', '宽带']),
    ('梧桐里', '西湖区', '一室一厅', 48, 3900, 3900, '季付', ['冰箱', '宽带']),
    ('江湾雅苑', '拱墅区', '三室两厅', 110, 7600, 7600, '年付', ['空调', '洗衣机', '冰箱', '宽带']),
]


class Command(BaseCommand):
    help = '写入演示账号、房源与租约（幂等，可重复执行）'

    def handle(self, *args, **options):
        users = {}
        for name, phone, role, qualifications in DEMO_USERS:
            users[phone], _ = User.objects.get_or_create(
                phone=phone,
                defaults={'name': name, 'role': role, 'qualifications': qualifications},
            )

        properties = {}
        for community, region, layout, area, rent, deposit, payment, facilities in DEMO_PROPERTIES:
            properties[community], _ = Property.objects.get_or_create(
                community=community,
                defaults={
                    'region': region, 'layout': layout, 'area': area, 'rent': rent,
                    'deposit': deposit, 'payment': payment, 'facilities': facilities,
                    'landlord_phone': '13800000001',
                },
            )

        today = datetime.date.today()
        leases = [
            ('13900000001', '海棠公寓', CONTRACT_ACTIVE, today - datetime.timedelta(days=180), today + datetime.timedelta(days=185)),
            ('13900000002', '梧桐里', CONTRACT_ACTIVE, today - datetime.timedelta(days=90), today + datetime.timedelta(days=275)),
            ('13900000001', '江湾雅苑', CONTRACT_EXPIRED, today - datetime.timedelta(days=720), today - datetime.timedelta(days=360)),
        ]
        for phone, community, status, start, end in leases:
            tenant = users[phone]
            Contract.objects.get_or_create(
                tenant=tenant, property=properties[community], start_date=start,
                defaults={
                    'landlord_name': '宋房东', 'rent': properties[community].rent,
                    'end_date': end, 'status': status,
                },
            )

        self.stdout.write(self.style.SUCCESS('演示数据已就绪'))
