from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.defaults import bad_request, page_not_found, server_error
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


def _plain(value):
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return str(value)


def error_payload(code: str, message: str, fields=None):
    error = {"code": code, "message": message}
    if fields:
        error["fields"] = _plain(fields)
    return {"error": error}


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    detail = data.get("detail") if isinstance(data, dict) else None
    if detail is not None:
        codes = exc.get_codes() if isinstance(exc, APIException) else None
        code = codes if isinstance(codes, str) else "request_error"
        message = str(detail)
        fields = None
    else:
        code = "validation_error"
        message = "Bitte korrigiere die markierten Eingaben."
        fields = data

    response.data = error_payload(code, message, fields)
    return response


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return JsonResponse(
            error_payload(
                "csrf_failed",
                "Die Sicherheitsprüfung ist fehlgeschlagen. Bitte lade die Seite neu.",
            ),
            status=403,
        )
    return django_csrf_failure(request, reason=reason)


def http_bad_request(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse(error_payload("bad_request", "Die Anfrage ist ungültig."), status=400)
    return bad_request(request, exception)


def http_not_found(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse(error_payload("not_found", "Die Ressource wurde nicht gefunden."), status=404)
    return page_not_found(request, exception)


def http_server_error(request):
    if request.path.startswith("/api/"):
        return JsonResponse(
            error_payload("server_error", "Die Anfrage konnte nicht verarbeitet werden."),
            status=500,
        )
    return server_error(request)


class InvalidCredentials(APIException):
    status_code = 400
    default_detail = "Anmeldedaten sind ungültig."
    default_code = "invalid_credentials"
