from rest_framework import serializers

from .models import House, Lease


class HouseSerializer(serializers.ModelSerializer):
    landlordPhone = serializers.CharField(source='landlord_phone')

    class Meta:
        model = House
        fields = [
            'id', 'community', 'region', 'layout', 'area', 'rent', 'deposit',
            'payment', 'facilities', 'status', 'landlordPhone',
        ]


class LeaseSerializer(serializers.ModelSerializer):
    house = HouseSerializer(read_only=True)
    active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lease
        fields = ['id', 'house', 'tenant', 'start_date', 'end_date', 'status', 'active', 'created_at']
