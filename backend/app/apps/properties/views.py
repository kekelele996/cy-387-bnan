from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.properties.models import Property
from app.apps.properties.serializers import PropertySerializer


class PropertyListView(APIView):
    def get(self, request):
        return Response(PropertySerializer(Property.objects.order_by('id'), many=True).data)
