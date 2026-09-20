"""报修模块权限。"""

from rest_framework.permissions import BasePermission

from app.constants.enums import ROLE_RESIDENT, ROLE_STAFF


class IsResident(BasePermission):
    message = '仅住户可操作'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ROLE_RESIDENT)


class IsStaff(BasePermission):
    message = '仅物业人员可操作'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ROLE_STAFF)
