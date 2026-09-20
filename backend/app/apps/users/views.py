from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.users.models import User
from app.apps.users.serializers import UserSerializer
from app.constants.errors import BizError
from app.utils.jwt import issue_token


class LoginView(APIView):
    """演示环境按手机号登录并签发 JWT。"""

    def post(self, request):
        phone = str(request.data.get('phone', '')).strip()
        user = User.objects.filter(phone=phone).first()
        if user is None:
            raise BizError('USER_NOT_FOUND', '用户不存在', 404)
        return Response({'token': issue_token(user), 'user': UserSerializer(user).data})


class UserListView(APIView):
    """演示环境列出可切换的账号。"""

    def get(self, request):
        return Response(UserSerializer(User.objects.order_by('id'), many=True).data)
