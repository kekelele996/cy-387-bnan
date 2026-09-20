from rest_framework.generics import ListAPIView

from .models import House
from .serializers import HouseSerializer


class HouseListView(ListAPIView):
    """房源列表（供报修时选择名下房屋等场景使用）。"""

    serializer_class = HouseSerializer

    def get_queryset(self):
        return House.objects.all()
