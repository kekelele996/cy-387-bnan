from rest_framework import serializers

from app.apps.contract.models import Contract


class ContractSerializer(serializers.ModelSerializer):
    propertyId = serializers.IntegerField(source='property_id')
    community = serializers.CharField(source='property.community')
    layout = serializers.CharField(source='property.layout')
    region = serializers.CharField(source='property.region')
    tenantName = serializers.CharField(source='tenant.name')
    landlordName = serializers.CharField(source='landlord_name')
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(source='end_date')

    class Meta:
        model = Contract
        fields = ['id', 'propertyId', 'community', 'layout', 'region', 'tenantName', 'landlordName', 'rent', 'startDate', 'endDate', 'status']
