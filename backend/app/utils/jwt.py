from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from app.constants.errors import BizError


def issue_token(user) -> str:
    """为用户签发访问令牌。"""
    token = AccessToken()
    token['user_id'] = user.id
    token['role'] = user.role
    return str(token)


def parse_user_id(raw_token: str) -> int:
    """解析令牌中的用户 ID，令牌无效时抛出业务异常。"""
    try:
        token = AccessToken(raw_token)
    except TokenError as exc:
        raise BizError('UNAUTHORIZED', '登录状态无效，请重新登录', 401) from exc
    return int(token['user_id'])
