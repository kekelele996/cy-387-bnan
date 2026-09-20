"""报修工单 HTTP 接口。

住户端：
- GET  /api/repairs/                 我的工单（含预计上门时间、轨迹）
- POST /api/repairs/                 提交报修（自动合并未关闭同类型工单）
- GET  /api/repairs/my-houses/       我名下有有效租约、可报修的房屋

物业台：
- GET  /api/repairs/desk/            全部工单（可按状态/故障类型筛选）
- POST /api/repairs/<id>/accept/     接单（自动匹配最少负载合格人员）
- POST /api/repairs/<id>/transfer/   转派
- POST /api/repairs/<id>/complete/   完工
"""

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.properties.serializers import HouseSerializer
from app.constants.enums import OPEN_TICKET_STATUS, REPAIR_TYPES, TICKET_STATUS

from .models import RepairTicket
from .permissions import IsResident, IsStaff
from .serializers import (
    AcceptSerializer,
    CompleteSerializer,
    RepairCreateSerializer,
    RepairTicketSerializer,
    TransferSerializer,
)
from .services import accept_ticket, complete_ticket, create_ticket, transfer_ticket


def _ok(data, status=200):
    return Response({'success': True, 'data': data, 'error': None}, status=status)


def _serialize_ticket(ticket_id):
    ticket = (
        RepairTicket.objects.select_related('house', 'reporter', 'assignee')
        .prefetch_related('logs__operator')
        .get(pk=ticket_id)
    )
    return RepairTicketSerializer(ticket).data


class MyHousesView(APIView):
    permission_classes = [IsResident]

    def get(self, request):
        houses = [
            lease.house
            for lease in request.user.leases.select_related('house').all()
            if lease.is_active
        ]
        return _ok(HouseSerializer(houses, many=True).data)


class RepairTicketListCreateView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        """住户只看自己名下工单。"""
        tickets = (
            RepairTicket.objects.filter(reporter=request.user)
            .select_related('house', 'reporter', 'assignee')
            .prefetch_related('logs__operator')
        )
        return _ok(RepairTicketSerializer(tickets, many=True).data)

    def post(self, request):
        if not request.user.is_resident:
            return _ok({'detail': '只有住户可以提交报修'}, status=403)
        serializer = RepairCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket, merged = create_ticket(
            reporter=request.user,
            house_id=serializer.validated_data['houseId'],
            fault_type=serializer.validated_data['faultType'],
            description=serializer.validated_data['description'],
            photo=serializer.validated_data.get('photo'),
        )
        data = _serialize_ticket(ticket.id)
        data['merged'] = merged
        return _ok(data, status=200 if merged else 201)


class StaffDeskView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        """物业工作台：可按状态、故障类型筛选。"""
        tickets = RepairTicket.objects.select_related('house', 'reporter', 'assignee').prefetch_related(
            'logs__operator'
        )
        status_filter = request.query_params.get('status')
        fault_filter = request.query_params.get('faultType')
        if status_filter == 'open':
            tickets = tickets.filter(status__in=OPEN_TICKET_STATUS)
        elif status_filter in TICKET_STATUS:
            tickets = tickets.filter(status=status_filter)
        if fault_filter in REPAIR_TYPES:
            tickets = tickets.filter(fault_type=fault_filter)
        return _ok(RepairTicketSerializer(tickets, many=True).data)


class AcceptTicketView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, ticket_id):
        serializer = AcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = accept_ticket(
            staff=request.user,
            ticket_id=ticket_id,
            expected_version=serializer.validated_data.get('version'),
            estimated_visit_at=serializer.validated_data.get('estimatedVisitAt'),
        )
        return _ok(_serialize_ticket(ticket.id))


class TransferTicketView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, ticket_id):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = transfer_ticket(
            staff=request.user,
            ticket_id=ticket_id,
            assignee_id=serializer.validated_data['assigneeId'],
            expected_version=serializer.validated_data.get('version'),
            note=serializer.validated_data.get('note', ''),
        )
        return _ok(_serialize_ticket(ticket.id))


class CompleteTicketView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, ticket_id):
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = complete_ticket(
            staff=request.user,
            ticket_id=ticket_id,
            expected_version=serializer.validated_data.get('version'),
            note=serializer.validated_data.get('note', ''),
        )
        return _ok(_serialize_ticket(ticket.id))
