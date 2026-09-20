from rest_framework import serializers

from app.apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'phone', 'role', 'qualifications']
