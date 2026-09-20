from django.urls import path

from .views import (
    AcceptTicketView,
    CompleteTicketView,
    MyHousesView,
    RepairTicketListCreateView,
    StaffDeskView,
    TransferTicketView,
)

urlpatterns = [
    path('', RepairTicketListCreateView.as_view()),
    path('my-houses/', MyHousesView.as_view()),
    path('desk/', StaffDeskView.as_view()),
    path('<int:ticket_id>/accept/', AcceptTicketView.as_view()),
    path('<int:ticket_id>/transfer/', TransferTicketView.as_view()),
    path('<int:ticket_id>/complete/', CompleteTicketView.as_view()),
]
