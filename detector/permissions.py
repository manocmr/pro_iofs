from django.conf import settings
from rest_framework.permissions import BasePermission


class HasAPIKey(BasePermission):
    message = "Clé API manquante ou invalide (header 'X-API-Key' requis)."

    def has_permission(self, request, view):
        return request.headers.get("X-API-Key") == settings.API_KEY
