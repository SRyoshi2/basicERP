from rest_framework.routers import DefaultRouter

from .views import BusinessDocumentViewSet

router = DefaultRouter()
router.register("", BusinessDocumentViewSet, basename="business-document")

urlpatterns = router.urls
