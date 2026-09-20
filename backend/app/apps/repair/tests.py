"""报修闭环领域规则与接口测试。"""

import threading
from datetime import timedelta

from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from app.apps.properties.models import House, Lease
from app.apps.repair.models import RepairTicket, TicketLog
from app.apps.repair import services
from app.apps.users.models import User
from app.constants.enums import (
    FAULT_APPLIANCE,
    FAULT_LOCK,
    FAULT_PLUMBING_ELECTRIC,
    LEASE_ACTIVE,
    LEASE_EXPIRED,
    ROLE_RESIDENT,
    ROLE_STAFF,
    TICKET_COMPLETED,
    TICKET_PENDING,
    TICKET_PROCESSING,
)
from app.utils.exception_handler import BusinessError


def _make_user(username, role, faults=None):
    user = User.objects.create(username=username, role=role, qualified_faults=faults or [])
    user.set_password('pw123456')
    user.save()
    return user


class RepairRuleTests(TestCase):
    def setUp(self):
        self.tenant = _make_user('tenant', ROLE_RESIDENT)
        self.outsider = _make_user('outsider', ROLE_RESIDENT)
        self.shui = _make_user('shui', ROLE_STAFF, [FAULT_PLUMBING_ELECTRIC])
        self.shui2 = _make_user('shui2', ROLE_STAFF, [FAULT_PLUMBING_ELECTRIC])
        self.suo = _make_user('suo', ROLE_STAFF, [FAULT_LOCK])
        self.house = House.objects.create(
            community='海棠公寓', region='滨江区', layout='两室一厅', area=76,
            rent=5200, deposit=5200, payment='月付',
        )
        today = timezone.localdate()
        Lease.objects.create(
            house=self.house, tenant=self.tenant, status=LEASE_ACTIVE,
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=300),
        )

    def test_only_active_lease_can_report(self):
        # 名下无租约被拒
        with self.assertRaises(BusinessError) as ctx:
            services.create_ticket(
                reporter=self.outsider, house_id=self.house.id,
                fault_type=FAULT_PLUMBING_ELECTRIC, description='厨房没电',
            )
        self.assertEqual(ctx.exception.code, 'NO_ACTIVE_LEASE')

        # 已到期租约同样被拒
        expired_house = House.objects.create(
            community='旧小区', region='西湖区', layout='一室', area=40,
            rent=3000, deposit=3000, payment='月付',
        )
        today = timezone.localdate()
        Lease.objects.create(
            house=expired_house, tenant=self.outsider, status=LEASE_EXPIRED,
            start_date=today - timedelta(days=200), end_date=today - timedelta(days=1),
        )
        with self.assertRaises(BusinessError) as ctx:
            services.create_ticket(
                reporter=self.outsider, house_id=expired_house.id,
                fault_type=FAULT_LOCK, description='门锁坏了',
            )
        self.assertEqual(ctx.exception.code, 'NO_ACTIVE_LEASE')

    def test_merge_open_ticket_same_house_fault(self):
        ticket1, merged1 = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='客厅插座没电',
        )
        self.assertFalse(merged1)
        self.assertEqual(ticket1.status, TICKET_PENDING)

        # 同房屋同类型再次提交 → 合并到原工单，不新建
        ticket2, merged2 = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='厨房也没电',
        )
        self.assertTrue(merged2)
        self.assertEqual(ticket1.id, ticket2.id)
        self.assertEqual(RepairTicket.objects.count(), 1)
        # 合并也留下轨迹
        self.assertTrue(TicketLog.objects.filter(ticket=ticket1, note__contains='补充报修').exists())

        # 不同故障类型不合并
        ticket3, merged3 = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_LOCK, description='入户门锁不上',
        )
        self.assertFalse(merged3)
        self.assertEqual(RepairTicket.objects.count(), 2)

        # 完工后同类型可以重新开单
        services.accept_ticket(staff=self.shui, ticket_id=ticket1.id)
        services.complete_ticket(staff=self.shui, ticket_id=ticket1.id)
        ticket4, merged4 = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='又跳闸了',
        )
        self.assertFalse(merged4)
        self.assertNotEqual(ticket4.id, ticket1.id)

    def test_accept_picks_least_loaded_qualified(self):
        # 直接构造 shui 已有 2 个处理中工单、shui2 空闲的负载分布
        for i in range(2):
            house = House.objects.create(
                community=f'小区{i}', region='区', layout='一室', area=40,
                rent=3000, deposit=3000, payment='月付',
            )
            Lease.objects.create(
                house=house, tenant=self.tenant, status=LEASE_ACTIVE,
                start_date=timezone.localdate() - timedelta(days=1),
                end_date=timezone.localdate() + timedelta(days=300),
            )
            services.create_ticket(
                reporter=self.tenant, house_id=house.id,
                fault_type=FAULT_PLUMBING_ELECTRIC, description=f'故障{i}',
            )
        RepairTicket.objects.filter(
            house_id__gt=self.house.id, fault_type=FAULT_PLUMBING_ELECTRIC
        ).update(assignee=self.shui, status=TICKET_PROCESSING)

        target, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='新故障',
        )
        # shui 负载更高，由 shui 接单应被拒
        with self.assertRaises(BusinessError) as ctx:
            services.accept_ticket(staff=self.shui, ticket_id=target.id)
        self.assertEqual(ctx.exception.code, 'STAFF_NOT_QUALIFIED')
        # 负载最少的 shui2 接单成功
        updated = services.accept_ticket(staff=self.shui2, ticket_id=target.id)
        self.assertEqual(updated.status, TICKET_PROCESSING)
        self.assertEqual(updated.assignee_id, self.shui2.id)
        self.assertIsNotNone(updated.estimated_visit_at)

    def test_unqualified_staff_rejected(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_LOCK, description='门锁坏',
        )
        # 水电工接锁类工单：本人无资质直接拒绝
        with self.assertRaises(BusinessError) as ctx:
            services.accept_ticket(staff=self.shui, ticket_id=ticket.id)
        self.assertEqual(ctx.exception.code, 'STAFF_NOT_QUALIFIED')
        self.assertEqual(ticket.status, TICKET_PENDING)

        # 平台上完全没有对应资质人员时给出明确错误
        with self.assertRaises(BusinessError) as ctx:
            services.choose_least_loaded_staff('管道')
        self.assertEqual(ctx.exception.code, 'NO_QUALIFIED_STAFF')

    def test_transfer_rules(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='漏水',
        )
        # 待受理不能转派
        with self.assertRaises(BusinessError) as ctx:
            services.transfer_ticket(staff=self.shui, ticket_id=ticket.id, assignee_id=self.shui2.id)
        self.assertEqual(ctx.exception.code, 'TICKET_NOT_PROCESSING')

        services.accept_ticket(staff=self.shui, ticket_id=ticket.id)

        # 非当前责任人不能转派
        with self.assertRaises(BusinessError) as ctx:
            services.transfer_ticket(staff=self.shui2, ticket_id=ticket.id, assignee_id=self.shui.id)
        self.assertEqual(ctx.exception.code, 'NOT_CURRENT_OWNER')

        # 不能转派给无资质人员（锁工无水电资质）
        with self.assertRaises(BusinessError) as ctx:
            services.transfer_ticket(staff=self.shui, ticket_id=ticket.id, assignee_id=self.suo.id)
        self.assertEqual(ctx.exception.code, 'STAFF_NOT_QUALIFIED')

        # 正常转派给有资质的 shui2
        updated = services.transfer_ticket(staff=self.shui, ticket_id=ticket.id, assignee_id=self.shui2.id)
        self.assertEqual(updated.assignee_id, self.shui2.id)
        self.assertEqual(updated.status, TICKET_PROCESSING)
        self.assertEqual(updated.version, 2)

        # 物业台用旧版本号（接单后 v=1）再次转派：冲突拒绝，责任人不变
        with self.assertRaises(BusinessError) as ctx:
            services.transfer_ticket(
                staff=self.shui2, ticket_id=ticket.id,
                assignee_id=self.shui.id, expected_version=1,
            )
        self.assertEqual(ctx.exception.code, 'CONFLICT')
        self.assertEqual(RepairTicket.objects.get(pk=ticket.id).assignee_id, self.shui2.id)

        # 转派后原责任人无权完工
        with self.assertRaises(BusinessError) as ctx:
            services.complete_ticket(staff=self.shui, ticket_id=ticket.id)
        self.assertEqual(ctx.exception.code, 'NOT_CURRENT_OWNER')

    def test_complete_rules(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='跳闸',
        )
        # 待受理不能完工
        with self.assertRaises(BusinessError) as ctx:
            services.complete_ticket(staff=self.shui, ticket_id=ticket.id)
        self.assertEqual(ctx.exception.code, 'TICKET_NOT_PROCESSING')

        services.accept_ticket(staff=self.shui, ticket_id=ticket.id)
        updated = services.complete_ticket(staff=self.shui, ticket_id=ticket.id, note='已更换空开')
        self.assertEqual(updated.status, TICKET_COMPLETED)
        self.assertIsNotNone(updated.completed_at)

        # 已完成再次完工/接单/转派全部拒绝
        with self.assertRaises(BusinessError) as ctx:
            services.complete_ticket(staff=self.shui, ticket_id=ticket.id)
        self.assertEqual(ctx.exception.code, 'TICKET_COMPLETED')
        with self.assertRaises(BusinessError) as ctx:
            services.accept_ticket(staff=self.shui2, ticket_id=ticket.id)
        self.assertEqual(ctx.exception.code, 'TICKET_COMPLETED')

    def test_stale_version_rejected(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='跳闸',
        )
        services.accept_ticket(staff=self.shui, ticket_id=ticket.id)  # version -> 1
        # 物业台拿着旧 version=0 完工
        with self.assertRaises(BusinessError) as ctx:
            services.complete_ticket(staff=self.shui, ticket_id=ticket.id, expected_version=0)
        self.assertEqual(ctx.exception.code, 'CONFLICT')
        self.assertEqual(RepairTicket.objects.get(pk=ticket.id).status, TICKET_PROCESSING)

    def test_every_status_change_writes_log(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='跳闸',
        )
        services.accept_ticket(staff=self.shui, ticket_id=ticket.id)
        services.transfer_ticket(staff=self.shui, ticket_id=ticket.id, assignee_id=self.shui2.id)
        services.complete_ticket(staff=self.shui2, ticket_id=ticket.id)
        actions = list(TicketLog.objects.filter(ticket=ticket).values_list('action', flat=True))
        self.assertEqual(actions, ['提交', '接单', '转派', '完工'])


@override_settings(DATABASES={'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': '/tmp/rentfind_concurrency.sqlite3',
    'OPTIONS': {'timeout': 30, 'transaction_mode': 'IMMEDIATE'},
}})
class RepairConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.tenant = _make_user('tenant', ROLE_RESIDENT)
        self.staff_a = _make_user('a_shui', ROLE_STAFF, [FAULT_APPLIANCE])
        self.staff_b = _make_user('b_shui', ROLE_STAFF, [FAULT_APPLIANCE])
        self.staff_c = _make_user('c_shui', ROLE_STAFF, [FAULT_APPLIANCE])
        self.house = House.objects.create(
            community='海棠公寓', region='滨江区', layout='两室一厅', area=76,
            rent=5200, deposit=5200, payment='月付',
        )
        today = timezone.localdate()
        Lease.objects.create(
            house=self.house, tenant=self.tenant, status=LEASE_ACTIVE,
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=300),
        )

    def test_concurrent_accept_complete_only_one_succeeds(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_APPLIANCE, description='空调不制冷',
        )
        # 同一责任人双线程并发抢同一张单：条件 UPDATE 只有一次成功
        results = {}
        barrier = threading.Barrier(2)

        def accept_worker(name):
            barrier.wait()
            try:
                services.accept_ticket(staff=self.staff_a, ticket_id=ticket.id)
                results[name] = 'ok'
            except BusinessError as exc:
                results[name] = exc.code
            except Exception as exc:  # noqa: BLE001
                results[name] = f'error:{type(exc).__name__}:{exc}'
            finally:
                connections.close_all()

        t1 = threading.Thread(target=accept_worker, args=('a',))
        t2 = threading.Thread(target=accept_worker, args=('b',))
        t1.start(); t2.start()
        t1.join(); t2.join()

        result_values = set(results.values())
        self.assertEqual(result_values, {'ok', 'TICKET_NOT_PENDING'}, results)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TICKET_PROCESSING)
        self.assertEqual(ticket.assignee_id, self.staff_a.id)
        self.assertEqual(ticket.version, 1)

        # 责任人与非责任人并发完工：只有当前责任人那一次成功
        complete_results = {}
        barrier = threading.Barrier(2)

        def complete_worker(name, staff):
            barrier.wait()
            try:
                services.complete_ticket(staff=staff, ticket_id=ticket.id)
                complete_results[name] = 'ok'
            except BusinessError as exc:
                complete_results[name] = exc.code
            except Exception as exc:  # noqa: BLE001
                complete_results[name] = f'error:{type(exc).__name__}:{exc}'
            finally:
                connections.close_all()

        t1 = threading.Thread(target=complete_worker, args=('owner', self.staff_a))
        t2 = threading.Thread(target=complete_worker, args=('other', self.staff_b))
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(complete_results['owner'], 'ok', complete_results)
        # 非责任人被拒：责任人已先行完工时表现为“已完成”，否则表现为“非当前责任人”
        self.assertIn(complete_results['other'], {'NOT_CURRENT_OWNER', 'TICKET_COMPLETED'}, complete_results)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TICKET_COMPLETED)
        self.assertEqual(ticket.version, 2)

    def test_concurrent_transfer_only_one_succeeds(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_APPLIANCE, description='冰箱不制冷',
        )
        services.accept_ticket(staff=self.staff_a, ticket_id=ticket.id)

        # 当前责任人同时发起两次转派（目标不同），只能有一次成功
        results = {}
        barrier = threading.Barrier(2)

        def transfer_worker(name, target):
            barrier.wait()
            try:
                services.transfer_ticket(
                    staff=self.staff_a, ticket_id=ticket.id, assignee_id=target.id
                )
                results[name] = 'ok'
            except BusinessError as exc:
                results[name] = exc.code
            except Exception as exc:  # noqa: BLE001
                results[name] = f'error:{type(exc).__name__}:{exc}'
            finally:
                connections.close_all()

        t1 = threading.Thread(target=transfer_worker, args=('to_b', self.staff_b))
        t2 = threading.Thread(target=transfer_worker, args=('to_c', self.staff_c))
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(set(results.values()), {'ok', 'NOT_CURRENT_OWNER'}, results)
        ticket.refresh_from_db()
        self.assertIn(ticket.assignee_id, {self.staff_b.id, self.staff_c.id})
        self.assertEqual(ticket.version, 2)  # 只有一次转派生效

    def test_concurrent_create_only_one_ticket(self):
        # 并发提交同房屋同类型：只有一张未关闭工单，另一请求合并
        results = {}
        barrier = threading.Barrier(2)

        def create_worker(name):
            barrier.wait()
            try:
                _, merged = services.create_ticket(
                    reporter=self.tenant, house_id=self.house.id,
                    fault_type=FAULT_APPLIANCE, description=f'报修{name}',
                )
                results[name] = 'merged' if merged else 'created'
            except Exception as exc:  # noqa: BLE001
                results[name] = f'error:{type(exc).__name__}:{exc}'
            finally:
                connections.close_all()

        t1 = threading.Thread(target=create_worker, args=('a',))
        t2 = threading.Thread(target=create_worker, args=('b',))
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(sorted(results.values()), ['created', 'merged'], results)
        self.assertEqual(
            RepairTicket.objects.filter(
                house=self.house, fault_type=FAULT_APPLIANCE, status__in=[TICKET_PENDING, TICKET_PROCESSING]
            ).count(),
            1,
        )


class RepairRollbackTests(TestCase):
    def setUp(self):
        self.tenant = _make_user('tenant', ROLE_RESIDENT)
        self.staff = _make_user('shui', ROLE_STAFF, [FAULT_PLUMBING_ELECTRIC])
        self.house = House.objects.create(
            community='海棠公寓', region='滨江区', layout='两室一厅', area=76,
            rent=5200, deposit=5200, payment='月付',
        )
        today = timezone.localdate()
        Lease.objects.create(
            house=self.house, tenant=self.tenant, status=LEASE_ACTIVE,
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=300),
        )

    def test_log_failure_rolls_back_status_change(self):
        ticket, _ = services.create_ticket(
            reporter=self.tenant, house_id=self.house.id,
            fault_type=FAULT_PLUMBING_ELECTRIC, description='跳闸',
        )
        original_create = TicketLog.objects.create

        def fail_on_accept(*args, **kwargs):
            if kwargs.get('action') == '接单':
                raise RuntimeError('模拟轨迹写入失败')
            return original_create(*args, **kwargs)

        TicketLog.objects.create = fail_on_accept
        try:
            with self.assertRaises(RuntimeError):
                services.accept_ticket(staff=self.staff, ticket_id=ticket.id)
        finally:
            TicketLog.objects.create = original_create

        ticket.refresh_from_db()
        # 任一步失败全部回滚：状态、责任人、版本都不变
        self.assertEqual(ticket.status, TICKET_PENDING)
        self.assertIsNone(ticket.assignee_id)
        self.assertEqual(ticket.version, 0)
        self.assertFalse(TicketLog.objects.filter(action='接单').exists())


class RepairApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = _make_user('tenant', ROLE_RESIDENT)
        self.stranger = _make_user('stranger', ROLE_RESIDENT)
        self.staff = _make_user('shui', ROLE_STAFF, [FAULT_PLUMBING_ELECTRIC])
        self.house = House.objects.create(
            community='海棠公寓', region='滨江区', layout='两室一厅', area=76,
            rent=5200, deposit=5200, payment='月付',
        )
        today = timezone.localdate()
        Lease.objects.create(
            house=self.house, tenant=self.tenant, status=LEASE_ACTIVE,
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=300),
        )

    def _login(self, user):
        self.client.force_authenticate(user=user)

    def test_full_loop_api_and_standard_envelope(self):
        self._login(self.tenant)
        resp = self.client.post('/api/repairs/', {
            'houseId': self.house.id, 'faultType': FAULT_PLUMBING_ELECTRIC, 'description': '卫生间漏水',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertTrue(body['success'])
        ticket_id = body['data']['id']
        self.assertEqual(body['data']['status'], TICKET_PENDING)

        # 住户端预计上门时间字段存在（接单前为空）
        resp = self.client.get('/api/repairs/')
        self.assertIsNone(resp.json()['data'][0]['estimatedVisitAt'])

        # 他人不能查看这张工单（住户端仅返回报修人自己的）
        self._login(self.stranger)
        resp = self.client.get('/api/repairs/')
        self.assertEqual(resp.json()['data'], [])

        # 非报修住户不能替别人房屋报修（跨租户拒绝）
        resp = self.client.post('/api/repairs/', {
            'houseId': self.house.id, 'faultType': FAULT_PLUMBING_ELECTRIC, 'description': '试试看',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error']['code'], 'NO_ACTIVE_LEASE')

        # 物业接单
        self._login(self.staff)
        resp = self.client.post(f'/api/repairs/{ticket_id}/accept/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], TICKET_PROCESSING)
        self.assertIsNotNone(resp.json()['data']['estimatedVisitAt'])

        # 物业台与接口数据一致
        resp = self.client.get('/api/repairs/desk/')
        ticket = next(item for item in resp.json()['data'] if item['id'] == ticket_id)
        self.assertEqual(ticket['status'], TICKET_PROCESSING)
        self.assertEqual(len(ticket['logs']), 2)

        # 完工
        resp = self.client.post(f'/api/repairs/{ticket_id}/complete/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], TICKET_COMPLETED)

        # 已完成操作被拒
        resp = self.client.post(f'/api/repairs/{ticket_id}/complete/', {}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['error']['code'], 'TICKET_COMPLETED')

        # 住户端轨迹完整、预计上门时间保留
        self._login(self.tenant)
        resp = self.client.get('/api/repairs/')
        data = resp.json()['data'][0]
        self.assertEqual(data['status'], TICKET_COMPLETED)
        self.assertEqual([log['action'] for log in data['logs']], ['提交', '接单', '完工'])
        self.assertIsNotNone(data['estimatedVisitAt'])

    def test_staff_only_endpoints(self):
        self._login(self.tenant)
        resp = self.client.get('/api/repairs/desk/')
        self.assertEqual(resp.status_code, 403)
