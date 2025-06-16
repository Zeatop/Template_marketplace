from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from .serializers import UserSerializer
from .models import User
# Create your views here.

class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retrieve the authenticated user's information."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)