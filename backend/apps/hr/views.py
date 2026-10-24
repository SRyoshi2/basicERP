from datetime import date

from django.contrib.auth import get_user_model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import User
from apps.core.permissions import HasCompletedPasswordChange, IsAdministrator
from apps.core.serializers import ApiErrorResponseSerializer

from .models import AbsenceRequest, LeaveEntitlement
from .serializers import (
    AbsenceCreateSerializer, AbsenceRequestAuditEventSerializer, AbsenceRequestSerializer,
    AbsenceReviewSerializer, AbsenceUpdateSerializer, LeaveBalanceSerializer,
    LeaveEntitlementSerializer, LeaveEntitlementWriteSerializer,
)
from .services import cancel_absence, leave_balance, review_absence


class AbsenceRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AbsenceRequest.objects.select_related("employee", "reviewed_by")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("year", OpenApiTypes.INT),
        OpenApiParameter("status", OpenApiTypes.STR, enum=AbsenceRequest.Status.values),
        OpenApiParameter("kind", OpenApiTypes.STR, enum=AbsenceRequest.Kind.values),
        OpenApiParameter("employee", OpenApiTypes.INT, description="Nur für Administratoren"),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=AbsenceCreateSerializer,
        responses={201: AbsenceRequestSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=AbsenceUpdateSerializer,
        responses={200: AbsenceRequestSerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return AbsenceCreateSerializer
        if self.action in {"update", "partial_update"}:
            return AbsenceUpdateSerializer
        return AbsenceRequestSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role != User.Role.ADMIN:
            queryset = queryset.filter(employee=self.request.user)
        elif employee := self.request.query_params.get("employee"):
            queryset = queryset.filter(employee_id=employee)
        if self.action == "list":
            if year := self.request.query_params.get("year"):
                if not year.isdigit() or not 2000 <= int(year) <= 2200:
                    return queryset.none()
                queryset = queryset.filter(start_date__year=int(year))
            if value := self.request.query_params.get("status"):
                if value in AbsenceRequest.Status.values:
                    queryset = queryset.filter(status=value)
            if value := self.request.query_params.get("kind"):
                if value in AbsenceRequest.Kind.values:
                    queryset = queryset.filter(kind=value)
        return queryset

    @extend_schema(
        request=AbsenceReviewSerializer,
        responses={200: AbsenceRequestSerializer, 400: ApiErrorResponseSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, HasCompletedPasswordChange, IsAdministrator])
    def review(self, request, pk=None):
        serializer = AbsenceReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            absence = review_absence(
                self.get_object().pk,
                serializer.validated_data["decision"],
                serializer.validated_data.get("decision_note", ""),
                request.user,
            )
        except ValueError as error:
            return Response(
                {"error": {"code": "invalid_state", "message": str(error)}}, status=400
            )
        return Response(AbsenceRequestSerializer(absence).data)

    @extend_schema(request=None, responses={200: AbsenceRequestSerializer, 400: ApiErrorResponseSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            absence = cancel_absence(
                self.get_object().pk, request.user, request.user.role == User.Role.ADMIN
            )
        except ValueError as error:
            return Response(
                {"error": {"code": "invalid_state", "message": str(error)}}, status=400
            )
        return Response(AbsenceRequestSerializer(absence).data)

    @extend_schema(responses={200: AbsenceRequestAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(
            AbsenceRequestAuditEventSerializer(
                self.get_object().audit_events.all(), many=True
            ).data
        )


class LeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]

    @extend_schema(
        parameters=[
            OpenApiParameter("year", OpenApiTypes.INT),
            OpenApiParameter("employee", OpenApiTypes.INT, description="Nur für Administratoren"),
        ],
        responses={200: LeaveBalanceSerializer},
    )
    def get(self, request):
        try:
            year = int(request.query_params.get("year", date.today().year))
        except ValueError:
            return Response(
                {"error": {"code": "validation_error", "message": "Jahr ist ungültig."}},
                status=400,
            )
        if not 2000 <= year <= 2200:
            return Response(
                {"error": {"code": "validation_error", "message": "Jahr ist ungültig."}},
                status=400,
            )
        employee = request.user
        if request.user.role == User.Role.ADMIN and request.query_params.get("employee"):
            employee = get_user_model().objects.filter(
                pk=request.query_params["employee"], is_active=True
            ).first()
            if employee is None:
                return Response(
                    {"error": {"code": "not_found", "message": "Mitarbeiter nicht gefunden."}},
                    status=404,
                )
        return Response(LeaveBalanceSerializer(leave_balance(employee, year)).data)


class LeaveEntitlementView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange, IsAdministrator]

    @extend_schema(
        parameters=[OpenApiParameter("year", OpenApiTypes.INT)],
        responses={200: LeaveEntitlementSerializer(many=True)},
    )
    def get(self, request):
        queryset = LeaveEntitlement.objects.select_related("employee")
        if year := request.query_params.get("year"):
            if not year.isdigit() or not 2000 <= int(year) <= 2200:
                return Response([])
            queryset = queryset.filter(year=int(year))
        return Response(LeaveEntitlementSerializer(queryset, many=True).data)

    @extend_schema(
        request=LeaveEntitlementWriteSerializer,
        responses={200: LeaveEntitlementSerializer, 201: LeaveEntitlementSerializer},
    )
    def post(self, request):
        existed = LeaveEntitlement.objects.filter(
            employee_id=request.data.get("employee"), year=request.data.get("year")
        ).exists()
        serializer = LeaveEntitlementWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        entitlement = serializer.save()
        return Response(
            LeaveEntitlementSerializer(entitlement).data,
            status=status.HTTP_200_OK if existed else status.HTTP_201_CREATED,
        )
