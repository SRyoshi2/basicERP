from rest_framework.routers import DefaultRouter

from .views import ContactImportViewSet, ContactViewSet

router = DefaultRouter()
router.register("contacts", ContactViewSet, basename="contact")
router.register("imports", ContactImportViewSet, basename="contact-import")

urlpatterns = router.urls
