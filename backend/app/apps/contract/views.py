from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.contract.models import Contract
from app.apps.contract.serializers import ContractSerializer
from app.apps.users.permissions import IsLoggedIn


class ContractListView(APIView):
    """返回当前用户名下的合同，租客报修时据此选择房屋。"""

    permission_classes = [IsLoggedIn]

    def get(self, request):
        contracts = Contract.objects.filter(tenant=request.user).select_related('property', 'tenant').order_by('-start_date')
        return Response(ContractSerializer(contracts, many=True).data)
