from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from .permissions import IsSuperUser
from django.contrib.auth import authenticate, login, logout
from .models import User
from .serializers import UserSerializer, AddressSerializer

class UserViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des utilisateurs."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        """Définit les permissions selon l'action."""
        if self.action == 'register':  # Inscription
            permission_classes = [AllowAny]
        elif self.action == 'update_profile':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """Inscription d'un nouvel utilisateur."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Utilisateur créé avec succès',
                'user_id': user.id,
                'user_mail': user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Récupère le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        """Met à jour le profil de l'utilisateur connecté."""
        serializer = self.get_serializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profil mis à jour',
                'user': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['delete'], permission_classes=[IsSuperUser])
    def delete_profile(self, request):
        """Supprime le profil utilisateur - propriétaire ou admin seulement."""
        email = request.data.get('email')
        if not email:
            return Response({
                'error': 'Email requis pour la suppression'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            user.delete()
            return Response({
                'message': 'Profil supprimé avec succès'
            }, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({
                'error': 'Utilisateur introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['delete'], permission_classes=[IsAuthenticated])
    def delete_me(self, request):
        """Supprime le profil utilisateur - propriétaire ou admin seulement."""
        password = request.data.get('password')
        if not password:
            return Response({
                'error': 'Mot de passe requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not request.user.check_password(password):
            return Response({
                'error': 'Mot de passe incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        request.user.delete()
        return Response({
            'message': 'Profil supprimé'
        }, status=status.HTTP_204_NO_CONTENT)

