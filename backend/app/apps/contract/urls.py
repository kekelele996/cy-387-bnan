from django.urls import path

from .views import ContractListView

urlpatterns = [
    path('', ContractListView.as_view()),
]
