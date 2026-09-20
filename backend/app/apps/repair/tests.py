import datetime
from unittest import mock

from django.utils import timezone
from rest_framework.test import APITestCase

from app.apps.contract.models import Contract
from app.apps.properties.models import Property
from app.apps.repair.models import RepairTicket, RepairTicketLog
from app.apps.repair.services import create_ticket, pick_assignee
from app.apps.users.models import User
from app.constants.enums import (
    ACTION_ACCEPT,
    ACTION_COMPLETE,
    ACTION_CREATE,
    ACTION_DISPATCH,
    ACTION_MERGE,
    ACTION_REASSIGN,
    CONTRACT_ACTIVE,
    ROLE_LANDLORD,
    ROLE_STAFF,
    ROLE_TENANT,
    STATUS_DONE,
    STATUS_PENDING,
    STATUS_PROCESSING,
)
from app.utils.jwt import issue_token


class RepairFlowTestCase(APITestCase):
    """报修受理闭环：租约校验、合并、派单、接单、转派、完工。"""

    @classmethod
    def setUpTestData(cls):
        cls.landlord = User.objects.create(name='宋房东', phone='13800000001', role=ROLE_LANDLORD)
        cls.tenant = User.objects.create(name='陈晨', phone='13900000001', role=ROLE_TENANT)
        cls.other_tenant = User.objects.create(name='林小', phone='13900000002', role=ROLE_TENANT)
        cls.staff_a = User.objects.create(name='张师傅', phone='13700000001', role=ROLE_STAFF, qualifications=['水电', '门锁'])
        cls.staff_b = User.objects.create(name='王师傅', phone='13700000002', role=ROLE_STAFF, qualifications=['水电', '管道'])
        cls.staff_c = User.objects.create(name='李师傅', phone='13700000003', role=ROLE_STAFF, qualifications=['其他'])
        cls.property = Property.objects.create(
            community='海棠公寓', region='滨江区', layout='两室一厅', area=76, rent=5200,
            deposit=5200, payment='月付', facilities=['空调'], landlord_phone='13800000001',
        )
        cls.other_property = Property.objects.create(
            community='梧桐里', region='西湖区', layout='一室一厅', area=48, rent=3900,
            deposit=3900, payment='季付', facilities=['宽带'], landlord_phone='13800000001',
        )
        today = timezone.localdate()
        Contract.objects.create(
            property=cls.property, tenant=cls.tenant, landlord_name='宋房东', rent=5200,
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=335),
            status=CONTRACT_ACTIVE,
        )

    def setUp(self):
        RepairTicket.objects.all().delete()
        RepairTicketLog.objects.all().delete()

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {issue_token(user)}')

    def create_via_api(self, user, property_id, fault_type='水电', description='厨房漏水'):
        self.auth(user)
        return self.client.post('/api/repairs/', {
            'propertyId': property_id, 'faultType': fault_type, 'description': description,
        }, format='json')

    # ---------- 租约校验 ----------

    def test_create_without_active_lease_rejected(self):
        response = self.create_via_api(self.other_tenant, self.property.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'LEASE_INVALID')
        self.assertEqual(RepairTicket.objects.count(), 0)

    def test_create_for_property_without_lease_rejected(self):
        response = self.create_via_api(self.tenant, self.other_property.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'LEASE_INVALID')

    def test_create_with_expired_lease_rejected(self):
        contract = Contract.objects.get(tenant=self.tenant, property=self.property)
        contract.end_date = timezone.localdate() - datetime.timedelta(days=1)
        contract.save()
        response = self.create_via_api(self.tenant, self.property.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'LEASE_INVALID')

    # ---------- 创建与自动派单 ----------

    def test_create_dispatches_to_qualified_least_busy_staff(self):
        response = self.create_via_api(self.tenant, self.property.id)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['merged'])
        ticket = RepairTicket.objects.get()
        # 张师傅、王师傅都具备水电资质，首单派给工单数相同、id 较小者
        self.assertEqual(ticket.assignee, self.staff_a)
        self.assertEqual(ticket.status, STATUS_PROCESSING)
        self.assertIsNotNone(ticket.expected_visit_at)
        actions = list(ticket.logs.values_list('action', flat=True))
        self.assertEqual(actions, [ACTION_CREATE, ACTION_DISPATCH])

    def test_dispatch_prefers_least_busy_staff(self):
        first = self.create_via_api(self.tenant, self.property.id, description='第一单')
        self.assertEqual(first.status_code, 201)
        # 张师傅已有 1 单未完成，第二单应派给王师傅
        tenant2 = self.other_tenant_lease()
        ticket2, merged = create_ticket(tenant=tenant2, property_obj=self.other_property,
                                        fault_type='水电', description='第二单', photos=[])
        self.assertFalse(merged)
        self.assertEqual(ticket2.assignee, self.staff_b)
        # 两人各积压 1 单时，按 id 次序派给张师傅
        self.assertEqual(pick_assignee('水电'), self.staff_a)

    def other_tenant_lease(self):
        today = timezone.localdate()
        Contract.objects.get_or_create(
            property=self.other_property, tenant=self.other_tenant,
            defaults={
                'landlord_name': '宋房东', 'rent': 3900,
                'start_date': today - datetime.timedelta(days=10),
                'end_date': today + datetime.timedelta(days=355),
                'status': CONTRACT_ACTIVE,
            },
        )
        return self.other_tenant

    def test_create_without_qualified_staff_stays_pending(self):
        response = self.create_via_api(self.tenant, self.property.id, fault_type='家电', description='冰箱不制冷')
        self.assertEqual(response.status_code, 201)
        ticket = RepairTicket.objects.get()
        self.assertEqual(ticket.status, STATUS_PENDING)
        self.assertIsNone(ticket.assignee)

    # ---------- 合并 ----------

    def test_duplicate_open_ticket_merges_into_original(self):
        first = self.create_via_api(self.tenant, self.property.id, description='第一次报修')
        second = self.create_via_api(self.tenant, self.property.id, description='补充：水更大了')
        self.assertEqual(second.status_code, 201)
        self.assertTrue(second.data['merged'])
        self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(RepairTicket.objects.count(), 1)
        ticket = RepairTicket.objects.get()
        self.assertIn('第一次报修', ticket.description)
        self.assertIn('【住户补充】补充：水更大了', ticket.description)
        self.assertTrue(ticket.logs.filter(action=ACTION_MERGE).exists())

    def test_closed_ticket_does_not_merge(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        ticket.status = STATUS_DONE
        ticket.save()
        response = self.create_via_api(self.tenant, self.property.id, description='再次漏水')
        self.assertFalse(response.data['merged'])
        self.assertEqual(RepairTicket.objects.count(), 2)

    def test_different_fault_type_does_not_merge(self):
        self.create_via_api(self.tenant, self.property.id, fault_type='水电')
        response = self.create_via_api(self.tenant, self.property.id, fault_type='门锁', description='门锁坏了')
        self.assertFalse(response.data['merged'])
        self.assertEqual(RepairTicket.objects.count(), 2)

    # ---------- 接单 ----------

    def test_accept_pending_ticket(self):
        self.create_via_api(self.tenant, self.property.id, fault_type='家电')
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_b)  # 王师傅无家电资质
        response = self.client.post(f'/api/repairs/{ticket.id}/accept/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'STAFF_UNQUALIFIED')

        self.auth(self.staff_c)  # 李师傅资质为「其他」，也无家电资质
        response = self.client.post(f'/api/repairs/{ticket.id}/accept/')
        self.assertEqual(response.status_code, 403)

        self.staff_c.qualifications = ['其他', '家电']
        self.staff_c.save()
        response = self.client.post(f'/api/repairs/{ticket.id}/accept/')
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_PROCESSING)
        self.assertEqual(ticket.assignee, self.staff_c)
        self.assertIsNotNone(ticket.expected_visit_at)
        self.assertTrue(ticket.logs.filter(action=ACTION_ACCEPT).exists())

    def test_concurrent_accept_only_one_succeeds(self):
        self.create_via_api(self.tenant, self.property.id, fault_type='家电')
        ticket = RepairTicket.objects.get()
        self.staff_c.qualifications = ['家电']
        self.staff_c.save()
        self.staff_b.qualifications = ['水电', '管道', '家电']
        self.staff_b.save()

        self.auth(self.staff_b)
        first = self.client.post(f'/api/repairs/{ticket.id}/accept/')
        self.auth(self.staff_c)
        second = self.client.post(f'/api/repairs/{ticket.id}/accept/')
        results = sorted([first.status_code, second.status_code])
        self.assertEqual(results, [200, 409])
        ticket.refresh_from_db()
        self.assertEqual(ticket.logs.filter(action=ACTION_ACCEPT).count(), 1)

    # ---------- 转派 ----------

    def test_reassign_only_by_current_assignee(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.assertEqual(ticket.assignee, self.staff_a)

        self.auth(self.staff_b)  # 非当前责任人
        response = self.client.post(f'/api/repairs/{ticket.id}/reassign/', {'targetStaffId': self.staff_c.id}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'TICKET_FORBIDDEN')

    def test_reassign_to_unqualified_staff_rejected(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_a)
        response = self.client.post(f'/api/repairs/{ticket.id}/reassign/', {'targetStaffId': self.staff_c.id}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'STAFF_UNQUALIFIED')
        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee, self.staff_a)
        self.assertFalse(ticket.logs.filter(action=ACTION_REASSIGN).exists())

    def test_reassign_success_updates_assignee_and_log(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_a)
        response = self.client.post(f'/api/repairs/{ticket.id}/reassign/',
                                    {'targetStaffId': self.staff_b.id, 'note': '现场需两人配合'}, format='json')
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assignee, self.staff_b)
        log = ticket.logs.get(action=ACTION_REASSIGN)
        self.assertEqual(log.operator, self.staff_a)
        self.assertEqual(log.note, '现场需两人配合')

    # ---------- 完工 ----------

    def test_complete_only_by_assignee(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_b)
        response = self.client.post(f'/api/repairs/{ticket.id}/complete/', {}, format='json')
        self.assertEqual(response.status_code, 403)

        self.auth(self.staff_a)
        response = self.client.post(f'/api/repairs/{ticket.id}/complete/', {'note': '已更换水管'}, format='json')
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_DONE)
        self.assertIsNotNone(ticket.completed_at)
        self.assertTrue(ticket.logs.filter(action=ACTION_COMPLETE).exists())

    def test_completed_ticket_rejects_further_operations(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_a)
        self.client.post(f'/api/repairs/{ticket.id}/complete/', {}, format='json')

        again = self.client.post(f'/api/repairs/{ticket.id}/complete/', {}, format='json')
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data['code'], 'TICKET_STATE_CONFLICT')

        reassign = self.client.post(f'/api/repairs/{ticket.id}/reassign/', {'targetStaffId': self.staff_b.id}, format='json')
        self.assertEqual(reassign.status_code, 409)
        self.assertEqual(RepairTicketLog.objects.filter(ticket=ticket, action=ACTION_COMPLETE).count(), 1)

    # ---------- 跨租户隔离 ----------

    def test_cross_tenant_access_denied(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()

        self.auth(self.other_tenant)
        detail = self.client.get(f'/api/repairs/{ticket.id}/')
        self.assertEqual(detail.status_code, 404)

        listing = self.client.get('/api/repairs/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 0)

    def test_tenant_cannot_use_staff_endpoints(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.tenant)
        response = self.client.post(f'/api/repairs/{ticket.id}/complete/', {}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_anonymous_rejected(self):
        response = self.client.get('/api/repairs/')
        self.assertEqual(response.status_code, 401)

    # ---------- 轨迹与预计上门时间 ----------

    def test_tenant_sees_expected_visit_time_and_trail(self):
        self.create_via_api(self.tenant, self.property.id)
        ticket = RepairTicket.objects.get()
        self.auth(self.staff_a)
        self.client.post(f'/api/repairs/{ticket.id}/complete/', {}, format='json')

        self.auth(self.tenant)
        detail = self.client.get(f'/api/repairs/{ticket.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertIsNotNone(detail.data['expectedVisitAt'])
        actions = [log['action'] for log in detail.data['logs']]
        self.assertEqual(actions, [ACTION_CREATE, ACTION_DISPATCH, ACTION_COMPLETE])

    # ---------- 事务回滚 ----------

    def test_create_rolls_back_when_any_step_fails(self):
        with mock.patch('app.apps.repair.services.RepairTicketLog.objects.create',
                        side_effect=RuntimeError('日志写入失败')):
            with self.assertRaises(RuntimeError):
                create_ticket(tenant=self.tenant, property_obj=self.property,
                              fault_type='水电', description='漏水', photos=[])
        self.assertEqual(RepairTicket.objects.count(), 0)
        self.assertEqual(RepairTicketLog.objects.count(), 0)

    def test_merge_rolls_back_when_log_fails(self):
        self.create_via_api(self.tenant, self.property.id, description='原始描述')
        original = RepairTicket.objects.get()
        with mock.patch('app.apps.repair.services.RepairTicketLog.objects.create',
                        side_effect=RuntimeError('日志写入失败')):
            with self.assertRaises(RuntimeError):
                create_ticket(tenant=self.tenant, property_obj=self.property,
                              fault_type='水电', description='补充描述', photos=[])
        original.refresh_from_db()
        self.assertEqual(original.description, '原始描述')
