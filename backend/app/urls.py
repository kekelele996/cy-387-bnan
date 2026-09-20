from django.urls import path

from app.apps.booking.views import BookingCreateView
from app.apps.contract.views import ContractListView
from app.apps.properties.views import PropertyListView
from app.apps.repair.views import (
    RepairAcceptView,
    RepairCompleteView,
    RepairReassignView,
    RepairStaffView,
    RepairTicketDetailView,
    RepairTicketView,
)
from app.apps.users.views import LoginView, UserListView

urlpatterns = [
    path('api/auth/login/', LoginView.as_view()),
    path('api/users/', UserListView.as_view()),
    path('api/properties/', PropertyListView.as_view()),
    path('api/bookings/', BookingCreateView.as_view()),
    path('api/contracts/', ContractListView.as_view()),
    path('api/repairs/', RepairTicketView.as_view()),
    path('api/repairs/staff/', RepairStaffView.as_view()),
    path('api/repairs/<int:pk>/', RepairTicketDetailView.as_view()),
    path('api/repairs/<int:pk>/accept/', RepairAcceptView.as_view()),
    path('api/repairs/<int:pk>/reassign/', RepairReassignView.as_view()),
    path('api/repairs/<int:pk>/complete/', RepairCompleteView.as_view()),
]
