from django.urls import include, path

urlpatterns = [
    path('api/auth/', include('app.apps.users.urls')),
    path('api/properties/', include('app.apps.properties.urls')),
    path('api/bookings/', include('app.apps.booking.urls')),
    path('api/contracts/', include('app.apps.contract.urls')),
    path('api/repairs/', include('app.apps.repair.urls')),
]
