from rest_framework import permissions

class IsSuperUser(permissions.BasePermission):
    """
    Custom permission pour n'autoriser l'accès qu'aux superutilisateurs.
    """
    def has_permission(self, request, view):
        # Vérifie si l'utilisateur est authentifié et est un superutilisateur
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)