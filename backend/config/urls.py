from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/crm/", include("apps.crm.urls")),
    path("api/v1/catalog/", include("apps.catalog.urls")),
    path("api/v1/projects/", include("apps.projects.urls")),
    path("api/v1/time/", include("apps.timetracking.urls")),
    path("api/v1/archive/", include("apps.archive.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

handler400 = "apps.core.errors.http_bad_request"
handler404 = "apps.core.errors.http_not_found"
handler500 = "apps.core.errors.http_server_error"
