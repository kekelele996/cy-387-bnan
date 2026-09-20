from rest_framework import serializers

from app.constants.enums import REPAIR_TYPES, ROLE_STAFF, USER_ROLES

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'phone', 'qualified_faults']


class StaffListSerializer(serializers.ModelSerializer):
    openCount = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'qualified_faults', 'openCount']

    def get_openCount(self, obj):
        from app.apps.repair.models import RepairTicket
        from app.constants.enums import OPEN_TICKET_STATUS

        return RepairTicket.objects.filter(assignee=obj, status__in=OPEN_TICKET_STATUS).count()


class RegisterSerializer(serializers.ModelSerializer):
    qualified_faults = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'phone', 'qualified_faults']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_role(self, value):
        if value not in USER_ROLES:
            raise serializers.ValidationError('角色不合法')
        return value

    def validate_qualified_faults(self, value):
        invalid = [item for item in value if item not in REPAIR_TYPES]
        if invalid:
            raise serializers.ValidationError(f'故障资质不合法：{invalid}')
        return value

    def validate(self, attrs):
        if attrs.get('role') == ROLE_STAFF and not attrs.get('qualified_faults'):
            raise serializers.ValidationError({'qualified_faults': '物业人员至少选择一项故障资质'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
