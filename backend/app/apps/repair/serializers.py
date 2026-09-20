"""报修工单序列化器。"""

from rest_framework import serializers

from app.constants.enums import REPAIR_TYPES

from .models import RepairTicket, TicketLog


class TicketLogSerializer(serializers.ModelSerializer):
    operatorName = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = TicketLog
        fields = ['id', 'action', 'operatorName', 'from_status', 'to_status', 'note', 'created_at']


class RepairTicketSerializer(serializers.ModelSerializer):
    faultType = serializers.CharField(source='fault_type')
    estimatedVisitAt = serializers.DateTimeField(source='estimated_visit_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    houseId = serializers.IntegerField(source='house_id', read_only=True)
    houseLabel = serializers.SerializerMethodField()
    reporterName = serializers.CharField(source='reporter.username', read_only=True)
    assigneeId = serializers.IntegerField(source='assignee_id', read_only=True)
    assigneeName = serializers.CharField(source='assignee.username', read_only=True, default=None)
    logs = TicketLogSerializer(many=True, read_only=True)
    merged = serializers.SerializerMethodField()

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'houseId', 'houseLabel', 'reporterName', 'faultType', 'description', 'photo',
            'status', 'assigneeId', 'assigneeName', 'estimatedVisitAt', 'completedAt',
            'version', 'createdAt', 'logs', 'merged',
        ]

    def get_houseLabel(self, obj):
        house = obj.house
        return f'{house.community} {house.layout}'

    def get_merged(self, obj):
        # 创建接口合并时由 service 注入到实例上，普通查询默认 False
        return getattr(obj, 'was_merged', False)


class RepairCreateSerializer(serializers.Serializer):
    houseId = serializers.IntegerField()
    faultType = serializers.CharField()
    description = serializers.CharField(min_length=2, max_length=500)
    photo = serializers.ImageField(required=False, allow_null=True)

    def validate_faultType(self, value):
        if value not in REPAIR_TYPES:
            raise serializers.ValidationError('故障类型不合法')
        return value

    def validate_description(self, value):
        return value.strip()


class AcceptSerializer(serializers.Serializer):
    # 乐观锁：前端持有的版本号
    version = serializers.IntegerField(required=False)
    estimatedVisitAt = serializers.DateTimeField(required=False, allow_null=True)


class TransferSerializer(serializers.Serializer):
    assigneeId = serializers.IntegerField()
    version = serializers.IntegerField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default='')


class CompleteSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default='')
