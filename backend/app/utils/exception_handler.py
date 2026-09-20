from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from app.constants.errors import BizError
from app.utils.logger import get_logger

logger = get_logger('exception')


def _error_response(code: str, message: str, status: int) -> Response:
    return Response({'success': False, 'code': code, 'message': message, 'data': None}, status=status)


def standard_exception_handler(exc, context):
    if isinstance(exc, BizError):
        return _error_response(exc.code, exc.message, exc.status)
    if isinstance(exc, ValidationError):
        return _error_response('VALIDATION_ERROR', _first_message(exc.detail), 400)
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return _error_response('UNAUTHORIZED', '请先登录', 401)
    if isinstance(exc, PermissionDenied):
        return _error_response('FORBIDDEN', str(exc.detail) if exc.detail else '没有操作权限', 403)
    response = exception_handler(exc, context)
    if response is not None:
        message = str(exc.detail) if hasattr(exc, 'detail') else '请求失败'
        return _error_response('REQUEST_ERROR', message, response.status_code)
    logger.exception('未处理的服务器异常: %s', exc)
    return _error_response('INTERNAL_ERROR', '服务器内部错误', 500)


def _first_message(detail) -> str:
    if isinstance(detail, dict):
        for value in detail.values():
            return _first_message(value)
    if isinstance(detail, (list, tuple)) and detail:
        return _first_message(detail[0])
    return str(detail)
