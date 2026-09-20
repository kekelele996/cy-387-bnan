"""认证相关视图：注册、登录、当前用户。"""

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from app.constants.enums import ROLE_STAFF
from app.utils.logger import get_logger

from .models import User
from .serializers import RegisterSerializer, StaffListSerializer, UserSerializer

logger = get_logger('users')


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info('用户注册成功 user=%s role=%s', user.username, user.role)
        return Response(
            {'success': True, 'data': UserSerializer(user).data, 'error': None},
            status=201,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        user = serializer.user
        logger.info('用户登录成功 user=%s role=%s', user.username, user.role)
        return Response(
            {
                'success': True,
                'data': {
                    'token': tokens['access'],
                    'refresh': tokens['refresh'],
                    'user': UserSerializer(user).data,
                },
                'error': None,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'success': True, 'data': UserSerializer(request.user).data, 'error': None})


class StaffListView(APIView):
    """物业人员名册（含资质与当前未完成工单数），供转派选择。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != ROLE_STAFF:
            return Response(
                {'success': False, 'data': None, 'error': {'code': 'FORBIDDEN', 'message': '仅物业人员可访问'}},
                status=403,
            )
        staff = User.objects.filter(role=ROLE_STAFF).order_by('id')
        return Response(
            {'success': True, 'data': StaffListSerializer(staff, many=True).data, 'error': None}
        )
