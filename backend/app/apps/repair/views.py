from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.properties.models import Property
from app.apps.users.models import User
from app.apps.users.permissions import IsLoggedIn, IsStaff
from app.constants.enums import ROLE_STAFF, ROLE_TENANT, STATUS_PENDING
from app.constants.errors import BizError

from .models import RepairTicket
from .serializers import (
    CreateTicketSerializer,
    NoteSerializer,
    ReassignSerializer,
    RepairTicketSerializer,
)
from .services import _unfinished_counts, accept_ticket, complete_ticket, create_ticket, reassign_ticket


def _visible_tickets(user):
    """按角色圈定可见工单：租客看自己的，物业看自己负责的和可接的。"""
    qs = RepairTicket.objects.select_related('property', 'tenant', 'assignee').prefetch_related('logs__operator')
    if user.role == ROLE_TENANT:
        return qs.filter(tenant=user)
    if user.role == ROLE_STAFF:
        return qs.filter(Q(assignee=user) | Q(status=STATUS_PENDING, fault_type__in=user.qualifications or []))
    return qs.none()


def _get_visible_ticket(user, ticket_id: int) -> RepairTicket:
    """跨租户或无权查看时一律按不存在处理。"""
    ticket = _visible_tickets(user).filter(pk=ticket_id).first()
    if ticket is None:
        raise BizError('TICKET_NOT_FOUND', '工单不存在或无权查看', 404)
    return ticket


class RepairTicketView(APIView):
    permission_classes = [IsLoggedIn]

    def get(self, request):
        return Response(RepairTicketSerializer(_visible_tickets(request.user), many=True).data)

    def post(self, request):
        if request.user.role != ROLE_TENANT:
            raise BizError('FORBIDDEN', '仅租客可提交报修', 403)
        serializer = CreateTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        property_obj = Property.objects.filter(pk=data['propertyId']).first()
        if property_obj is None:
            raise BizError('PROPERTY_NOT_FOUND', '房屋不存在', 404)
        ticket, merged = create_ticket(
            tenant=request.user, property_obj=property_obj, fault_type=data['faultType'],
            description=data['description'], photos=data['photos'],
        )
        payload = RepairTicketSerializer(ticket).data
        payload['merged'] = merged
        return Response(payload, status=201)


class RepairTicketDetailView(APIView):
    permission_classes = [IsLoggedIn]

    def get(self, request, pk):
        return Response(RepairTicketSerializer(_get_visible_ticket(request.user, pk)).data)


class RepairAcceptView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        ticket = accept_ticket(staff=request.user, ticket_id=pk)
        return Response(RepairTicketSerializer(ticket).data)


class RepairReassignView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        serializer = ReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = reassign_ticket(
            operator=request.user, ticket_id=pk,
            target_staff_id=serializer.validated_data['targetStaffId'],
            note=serializer.validated_data['note'],
        )
        return Response(RepairTicketSerializer(ticket).data)


class RepairCompleteView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = complete_ticket(operator=request.user, ticket_id=pk, note=serializer.validated_data['note'])
        return Response(RepairTicketSerializer(ticket).data)


class RepairStaffView(APIView):
    """列出物业人员及其未完成工单数，供转派选择。"""

    permission_classes = [IsStaff]

    def get(self, request):
        counts = _unfinished_counts()
        staff_list = User.objects.filter(role=ROLE_STAFF).order_by('id')
        data = [
            {
                'id': staff.id,
                'name': staff.name,
                'qualifications': staff.qualifications,
                'unfinishedCount': counts.get(staff.id, 0),
            }
            for staff in staff_list
        ]
        return Response(data)
