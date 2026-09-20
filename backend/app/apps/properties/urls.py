from django.urls import path

from .views import HouseListView

urlpatterns = [
    path('', HouseListView.as_view()),
]
