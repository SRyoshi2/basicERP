from rest_framework.routers import DefaultRouter

from .views import IncomingInvoiceViewSet

router = DefaultRouter()
router.register("incoming-invoices", IncomingInvoiceViewSet, basename="incoming-invoice")

urlpatterns = router.urls
