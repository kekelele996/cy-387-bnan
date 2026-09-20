from rest_framework import serializers

from app.constants.enums import REPAIR_TYPES

from .models import RepairTicket, RepairTicketLog


class RepairTicketLogSerializer(serializers.ModelSerializer):
    operatorName = serializers.SerializerMethodField()
    fromStatus = serializers.CharField(source='from_status')
    toStatus = serializers.CharField(source='to_status')
    createdAt = serializers.DateTimeField(source='created_at')

    class Meta:
        model = RepairTicketLog
        fields = ['id', 'action', 'operatorName', 'fromStatus', 'toStatus', 'note', 'createdAt']

    def get_operatorName(self, obj):
        return obj.operator.name if obj.operator else '系统'


class RepairTicketSerializer(serializers.ModelSerializer):
    faultType = serializers.CharField(source='fault_type')
    propertyId = serializers.IntegerField(source='property_id')
    community = serializers.CharField(source='property.community')
    tenantName = serializers.CharField(source='tenant.name')
    assigneeId = serializers.IntegerField(source='assignee_id', allow_null=True)
    assigneeName = serializers.SerializerMethodField()
    expectedVisitAt = serializers.DateTimeField(source='expected_visit_at')
    createdAt = serializers.DateTimeField(source='created_at')
    updatedAt = serializers.DateTimeField(source='updated_at')
    completedAt = serializers.DateTimeField(source='completed_at')
    logs = RepairTicketLogSerializer(many=True, read_only=True)

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'propertyId', 'community', 'faultType', 'description', 'photos', 'status',
            'tenantName', 'assigneeId', 'assigneeName', 'expectedVisitAt', 'version',
            'createdAt', 'updatedAt', 'completedAt', 'logs',
        ]

    def get_assigneeName(self, obj):
        return obj.assignee.name if obj.assignee else '待分配'


class CreateTicketSerializer(serializers.Serializer):
    propertyId = serializers.IntegerField(min_value=1)
    faultType = serializers.ChoiceField(choices=REPAIR_TYPES)
    description = serializers.CharField(max_length=500, trim_whitespace=True)
    photos = serializers.ListField(child=serializers.CharField(max_length=200), required=False, default=list)

    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError('故障描述不能为空')
        return value


class ReassignSerializer(serializers.Serializer):
    targetStaffId = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
