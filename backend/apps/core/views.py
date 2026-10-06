from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ChangePasswordSerializer,
    CompanyProfileSerializer,
    ApiErrorResponseSerializer,
    CsrfTokenSerializer,
    HealthSerializer,
    LoginSerializer,
    UserSerializer,
)
from .models import CompanyProfile
from .errors import InvalidCredentials
from .permissions import HasCompletedPasswordChange, IsAdministrator


def user_payload(user):
    return {
        "id": str(user.pk),
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "is_staff": user.is_staff,
        "must_change_password": user.must_change_password,
    }


class LiveHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthSerializer)
    def get(self, request):
        return Response({"status": "ok"})


class ReadyHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthSerializer)
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({"status": "ready"})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=CsrfTokenSerializer)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: UserSerializer, 400: ApiErrorResponseSerializer, 403: ApiErrorResponseSerializer},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["identifier"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise InvalidCredentials
        login(request, user)
        return Response(user_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(user_payload(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: UserSerializer, 400: ApiErrorResponseSerializer},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        login(request, request.user)
        return Response(user_payload(request.user))


class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        permissions = list(self.permission_classes)
        if self.request.method in {"PATCH", "PUT"}:
            permissions.append(IsAdministrator)
        return [permission() for permission in permissions]

    def get_object(self):
        company, _ = CompanyProfile.objects.get_or_create(pk=1)
        return company

    @extend_schema(
        responses={200: CompanyProfileSerializer, 401: ApiErrorResponseSerializer},
    )
    def get(self, request):
        return Response(CompanyProfileSerializer(self.get_object()).data)

    @extend_schema(
        request=CompanyProfileSerializer,
        responses={
            200: CompanyProfileSerializer,
            400: ApiErrorResponseSerializer,
            401: ApiErrorResponseSerializer,
            403: ApiErrorResponseSerializer,
        },
    )
    def patch(self, request):
        company = self.get_object()
        serializer = CompanyProfileSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)
