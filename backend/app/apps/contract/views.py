from rest_framework.response import Response
from rest_framework.views import APIView


class ContractListView(APIView):
    def get(self, request):
        data = [{'id': 1, 'tenant': '陈晨', 'landlord': '宋房东', 'rent': 5200, 'status': '待确认'}]
        return Response({'success': True, 'data': data, 'error': None})
