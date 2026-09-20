"""DRF 统一异常处理：所有错误响应保持同一结构。"""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from app.constants.errors import ERROR_CODES


def _envelope(code, message, status_code, details=None):
    error = {'code': code, 'message': message}
    if details is not None:
        error['details'] = details
    return Response({'success': False, 'data': None, 'error': error}, status=status_code)


class BusinessError(Exception):
    """业务规则校验失败时抛出，由统一异常处理转换为标准响应。"""

    def __init__(self, code, message=None, status_code=None, details=None):
        default_status, default_message = ERROR_CODES.get(code, (400, '业务处理失败'))
        self.code = code
        self.message = message or default_message
        self.status_code = status_code or default_status
        self.details = details
        super().__init__(self.message)


def standard_exception_handler(exc, context):
    # 业务自定义异常
    if isinstance(exc, BusinessError):
        return _envelope(exc.code, exc.message, exc.status_code, exc.details)

    # 数据库唯一约束冲突统一视作 409（并发合并等场景）
    if isinstance(exc, IntegrityError):
        status_code, message = ERROR_CODES['CONFLICT']
        return _envelope('CONFLICT', message, status_code)

    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, ValidationError):
        _, message = ERROR_CODES['VALIDATION_ERROR']
        return _envelope('VALIDATION_ERROR', message, status.HTTP_400_BAD_REQUEST, response.data)

    code = 'ERROR'
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        code = 'UNAUTHORIZED'
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        code = 'FORBIDDEN'
    elif response.status_code == status.HTTP_404_NOT_FOUND:
        code = 'NOT_FOUND'
    return _envelope(code, str(getattr(exc, 'detail', '请求失败')), response.status_code)
