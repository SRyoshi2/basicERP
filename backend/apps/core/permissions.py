from rest_framework.permissions import BasePermission


class HasCompletedPasswordChange(BasePermission):
    message = "Vor der weiteren Nutzung muss das Initialpasswort geändert werden."

    def has_permission(self, request, view):
        user = request.user
        return not user.is_authenticated or not user.must_change_password


class IsAdministrator(BasePermission):
    message = "Diese Aktion ist Administratoren vorbehalten."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.role == user.Role.ADMIN
