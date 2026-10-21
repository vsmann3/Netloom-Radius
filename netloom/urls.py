from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("api/tenants/<uuid:tenant_id>/subscribers/", views.subscribers, name="subscribers"),
    path("api/tenants/<uuid:tenant_id>/subscribers/<uuid:subscriber_id>/suspend/", views.suspend, name="suspend"),
]
