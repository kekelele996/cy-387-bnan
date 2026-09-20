from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from app.apps.users.models import User
from app.utils.jwt import parse_user_id


class JWTAuthentication(BaseAuthentication):
    """从 Authorization: Bearer <token> 中解析当前用户。"""

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None
        user_id = parse_user_id(header[7:].strip())
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise AuthenticationFailed('用户不存在或已被删除')
        return (user, None)
