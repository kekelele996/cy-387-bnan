from rest_framework.permissions import BasePermission

from app.apps.users.models import User
from app.constants.enums import ROLE_STAFF, ROLE_TENANT


class IsLoggedIn(BasePermission):
    message = '请先登录'

    def has_permission(self, request, view):
        return isinstance(request.user, User)


class IsTenant(BasePermission):
    message = '仅租客可执行该操作'

    def has_permission(self, request, view):
        return isinstance(request.user, User) and request.user.role == ROLE_TENANT


class IsStaff(BasePermission):
    message = '仅物业人员可执行该操作'

    def has_permission(self, request, view):
        return isinstance(request.user, User) and request.user.role == ROLE_STAFF
