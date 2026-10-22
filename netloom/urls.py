from django.contrib.auth import views as auth_views
from django.urls import path

from core import views
from core import caf_catalog
from core import caf_provisioning
from core import caf_settings

urlpatterns = [
    path("api/integrations/ecaf/v1/connection-status", caf_settings.connection_status, name="caf-connection-status"),
    path("companies/<int:company_id>/integrations/caf/", caf_settings.connection_settings, name="caf-connection-settings"),
    path("api/integrations/ecaf/v1/username-reservations", caf_provisioning.reservations, name="caf-reservations"),
    path("api/integrations/ecaf/v1/username-reservations/<uuid:reservation_id>/renew", caf_provisioning.renew_reservation, name="caf-reservation-renew"),
    path("api/integrations/ecaf/v2/provisionings", caf_provisioning.provisionings, name="caf-provisionings"),
    path("api/integrations/ecaf/v2/provisionings/<uuid:delivery_id>", caf_provisioning.receipt, name="caf-provisioning-receipt"),
    path("api/integrations/ecaf/v1/companies/<str:radius_company_id>/plans", caf_catalog.plans, name="caf-plans"),
    path("health/", views.health, name="health"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("companies/<int:company_id>/", views.company, name="company"),
    path("companies/<int:company_id>/users/", views.company, {"section": "subscribers"}, name="company-users"),
    path("companies/<int:company_id>/onboard/", views.caf_onboard, name="caf-onboard"),
    path("companies/<int:company_id>/plans/", views.company, {"section": "plans"}, name="company-plans"),
    path("companies/<int:company_id>/routers/", views.company, {"section": "routers"}, name="company-routers"),
    path("companies/<int:company_id>/subscribers/<uuid:subscriber_id>/suspend/", views.suspend_from_company, name="company-suspend"),
    path("companies/<uuid:tenant_id>/", views.company_legacy, name="company-legacy"),
    path("companies/<uuid:tenant_id>/subscribers/<uuid:subscriber_id>/suspend/", views.suspend_from_company, name="company-suspend-legacy"),
    path("api/tenants/<uuid:tenant_id>/subscribers/", views.subscribers, name="subscribers"),
    path("api/tenants/<uuid:tenant_id>/subscribers/<uuid:subscriber_id>/suspend/", views.suspend, name="suspend"),
]
