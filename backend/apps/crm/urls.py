from rest_framework.routers import DefaultRouter

from .views import ContactActivityViewSet, ContactImportViewSet, ContactViewSet

router = DefaultRouter()
router.register("contacts", ContactViewSet, basename="contact")
router.register("imports", ContactImportViewSet, basename="contact-import")
router.register("activities", ContactActivityViewSet, basename="contact-activity")

urlpatterns = router.urls
