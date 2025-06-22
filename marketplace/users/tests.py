"""
Tests unitaires et fonctionnels pour l'application User
=======================================================

Ce fichier contient tous les tests pour :
- Modèles : User, Address
- Serializers : UserSerializer, AddressSerializer  
- Vues : UserViewSet avec toutes ses actions

Organisation :
1. Tests unitaires (composants individuels)
2. Tests fonctionnels (API endpoints complets)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

from .models import User, Address, UserRole, Permissions
from .permissions import IsSuperUser
from .serializers import UserSerializer, AddressSerializer


# =============================================================================
# TESTS UNITAIRES
# =============================================================================

class AddressModelTests(TestCase):
    """Tests unitaires pour le modèle Address."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.address_data = {
            'street': '123 Rue de la Paix',
            'city': 'Paris',
            'postal_code': '75001',
            'country': 'France'
        }
    
    def test_address_creation(self):
        """Test de création d'une adresse valide."""
        address = Address.objects.create(**self.address_data)
        
        self.assertEqual(address.street, '123 Rue de la Paix')
        self.assertEqual(address.city, 'Paris')
        self.assertEqual(address.postal_code, '75001')
        self.assertEqual(address.country, 'France')
    
    def test_address_str_representation(self):
        """Test de la représentation string d'une adresse."""
        address = Address.objects.create(**self.address_data)
        expected = "123 Rue de la Paix, Paris, 75001, France"
        
        self.assertEqual(str(address), expected)
    
    def test_address_verbose_names(self):
        """Test des verbose names du modèle."""
        address = Address(**self.address_data)
        
        self.assertEqual(address._meta.get_field('street').verbose_name, 'Rue')
        self.assertEqual(address._meta.get_field('city').verbose_name, 'Ville')
        self.assertEqual(address._meta.get_field('postal_code').verbose_name, 'Code Postal')
        self.assertEqual(address._meta.get_field('country').verbose_name, 'Pays')


class UserModelTests(TestCase):
    """Tests unitaires pour le modèle User."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'name': 'Test',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.CLIENT.value
        }
        
        self.address_data = {
            'street': '123 Test Street',
            'city': 'TestCity',
            'postal_code': '12345',
            'country': 'TestCountry'
        }
    
    def test_user_creation_basic(self):
        """Test de création d'un utilisateur basique."""
        user = User.create_user(self.user_data.copy())
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test')
        self.assertEqual(user.surname, 'User')
        self.assertEqual(user.phone, '0123456789')
        self.assertEqual(user.role, UserRole.CLIENT.value)
        self.assertTrue(user.check_password('testpassword123'))
    
    def test_user_creation_with_address(self):
        """Test de création d'un utilisateur avec adresse."""
        user_data = self.user_data.copy()
        user_data['address'] = self.address_data
        
        user = User.create_user(user_data)
        
        self.assertIsNotNone(user.address)
        self.assertEqual(user.address.street, '123 Test Street')
        self.assertEqual(user.address.city, 'TestCity')
    
    def test_user_role_permissions(self):
        """Test des permissions selon les rôles."""
        # Test CLIENT
        client_data = self.user_data.copy()
        client = User.create_user(client_data)
        
        self.assertEqual(client.get_permission, Permissions.CLIENT)
        self.assertTrue(client.is_client())
        self.assertFalse(client.is_worker())
        self.assertFalse(client.is_admin())
        self.assertFalse(client.is_staff)
        self.assertFalse(client.is_superuser)
        
        # Test WORKER
        worker_data = self.user_data.copy()
        worker_data['email'] = 'worker@example.com'
        worker_data['role'] = UserRole.WORKER.value
        worker = User.create_user(worker_data)
        
        self.assertEqual(worker.get_permission, Permissions.WORKER)
        self.assertTrue(worker.is_worker())
        self.assertFalse(worker.is_client())
        self.assertFalse(worker.is_admin())
        self.assertTrue(worker.is_staff)
        self.assertFalse(worker.is_superuser)
        
        # Test ADMIN
        admin_data = self.user_data.copy()
        admin_data['email'] = 'admin@example.com'
        admin_data['role'] = UserRole.ADMIN.value
        admin = User.create_user(admin_data)
        
        self.assertEqual(admin.get_permission, Permissions.ADMIN)
        self.assertTrue(admin.is_admin())
        self.assertFalse(admin.is_client())
        self.assertFalse(admin.is_worker())
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
    
    def test_user_email_uniqueness(self):
        """Test de l'unicité des emails."""
        User.create_user(self.user_data.copy())
        
        with self.assertRaises(IntegrityError):
            User.create_user(self.user_data.copy())
    
    def test_user_str_representation(self):
        """Test de la représentation string d'un utilisateur."""
        user = User.create_user(self.user_data.copy())
        self.assertEqual(str(user), 'test@example.com')
    
    def test_user_access_methods(self):
        """Test des méthodes d'accès aux permissions."""
        admin_data = self.user_data.copy()
        admin_data['email'] = 'admin@example.com'
        admin_data['role'] = UserRole.ADMIN.value
        admin = User.create_user(admin_data)
        
        self.assertTrue(admin.has_admin_access())
        self.assertTrue(admin.has_staff_access())
        
        client = User.create_user(self.user_data.copy())
        self.assertFalse(client.has_admin_access())
        self.assertFalse(client.has_staff_access())


class AddressSerializerTests(TestCase):
    """Tests unitaires pour AddressSerializer."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.valid_address_data = {
            'street': '123 Test Street',
            'city': 'TestCity',
            'postal_code': '12345',
            'country': 'TestCountry'
        }
    
    def test_valid_address_serialization(self):
        """Test de sérialisation d'une adresse valide."""
        serializer = AddressSerializer(data=self.valid_address_data)
        
        self.assertTrue(serializer.is_valid())
        address = serializer.save()
        
        self.assertEqual(address.street, '123 Test Street')
        self.assertEqual(address.city, 'TestCity')
    
    def test_address_validation_missing_fields(self):
        """Test de validation avec des champs manquants."""
        # Test sans street
        invalid_data = self.valid_address_data.copy()
        del invalid_data['street']
        serializer = AddressSerializer(data=invalid_data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('This field is required.', str(serializer.errors))  # ✅ Message Django par défaut
        
        # Test sans city
        invalid_data = self.valid_address_data.copy()
        del invalid_data['city']
        serializer = AddressSerializer(data=invalid_data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('This field is required.', str(serializer.errors))


class UserSerializerTests(TestCase):
    """Tests unitaires pour UserSerializer."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.valid_user_data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'name': 'Test',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.CLIENT.value
        }
        
        self.address_data = {
            'street': '123 Test Street',
            'city': 'TestCity',
            'postal_code': '12345',
            'country': 'TestCountry'
        }
    
    def test_valid_user_serialization(self):
        """Test de sérialisation d'un utilisateur valide."""
        serializer = UserSerializer(data=self.valid_user_data)
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test')
        self.assertTrue(user.check_password('testpassword123'))
    
    def test_user_serialization_with_address(self):
        """Test de sérialisation d'un utilisateur avec adresse."""
        user_data = self.valid_user_data.copy()
        user_data['address'] = self.address_data
        
        serializer = UserSerializer(data=user_data)
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertIsNotNone(user.address)
        self.assertEqual(user.address.street, '123 Test Street')
    
    def test_email_validation_duplicate(self):
        """Test de validation d'email dupliqué."""
        # Créer un premier utilisateur
        User.create_user(self.valid_user_data.copy())
        
        # Tenter de créer un second avec le même email
        serializer = UserSerializer(data=self.valid_user_data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
    
    def test_email_validation_update_same_email(self):
        """Test de validation lors de mise à jour avec le même email."""
        user = User.create_user(self.valid_user_data.copy())
        
        # Mise à jour avec le même email (devrait être valide)
        update_data = {'name': 'Updated Name'}
        serializer = UserSerializer(user, data=update_data, partial=True)
        
        self.assertTrue(serializer.is_valid())
    
    def test_password_validation(self):
        """Test de validation du mot de passe."""
        invalid_data = self.valid_user_data.copy()
        invalid_data['password'] = '123'  # Trop court
        
        serializer = UserSerializer(data=invalid_data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
    
    def test_user_update(self):
        """Test de mise à jour d'un utilisateur."""
        user = User.create_user(self.valid_user_data.copy())
        
        update_data = {
            'name': 'Updated Name',
            'phone': '9876543210'
        }
        
        serializer = UserSerializer(user, data=update_data, partial=True)
        
        self.assertTrue(serializer.is_valid())
        updated_user = serializer.save()
        
        self.assertEqual(updated_user.name, 'Updated Name')
        self.assertEqual(updated_user.phone, '9876543210')


# =============================================================================
# TESTS FONCTIONNELS (API)
# =============================================================================

class UserAPITests(APITestCase):
    """Tests fonctionnels pour l'API User."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.client = APIClient()
        
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'name': 'Test',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.CLIENT.value
        }
        
        self.admin_data = {
            'email': 'admin@example.com',
            'password': 'adminpassword123',
            'name': 'Admin',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.ADMIN.value
        }
        
        # Créer des utilisateurs de test
        self.user = User.create_user(self.user_data.copy())
        self.admin = User.create_user(self.admin_data.copy())
        
        # Tokens JWT
        self.user_token = str(RefreshToken.for_user(self.user).access_token)
        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)
    
    def authenticate_user(self, token):
        """Helper pour authentifier un utilisateur."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def test_user_registration(self):
        """Test d'inscription d'un nouvel utilisateur."""
        new_user_data = {
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'name': 'New',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.CLIENT.value
        }
        
        response = self.client.post('/api/users/register/', new_user_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user_id', response.data)
        self.assertEqual(response.data['user_mail'], 'newuser@example.com')
        
        # Vérifier que l'utilisateur a été créé
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
    
    def test_user_registration_duplicate_email(self):
        """Test d'inscription avec un email déjà utilisé."""
        response = self.client.post('/api/users/register/', self.user_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_user_registration_invalid_password(self):
        """Test d'inscription avec un mot de passe invalide."""
        invalid_data = self.user_data.copy()
        invalid_data['email'] = 'invalid@example.com'
        invalid_data['password'] = '123'  # Trop court
        
        response = self.client.post('/api/users/register/', invalid_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
    
    def test_get_user_profile_authenticated(self):
        """Test de récupération du profil utilisateur (authentifié)."""
        self.authenticate_user(self.user_token)
        
        response = self.client.get('/api/users/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['name'], 'Test')
        self.assertNotIn('password', response.data)  # Password ne doit pas être exposé
    
    def test_get_user_profile_unauthenticated(self):
        """Test de récupération du profil sans authentification."""
        response = self.client.get('/api/users/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_user_profile(self):
        """Test de mise à jour du profil utilisateur."""
        self.authenticate_user(self.user_token)
        
        update_data = {
            'name': 'Updated Name',
            'phone': '9876543210'
        }
        
        response = self.client.put('/api/users/update_profile/', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['user']['name'], 'Updated Name')
        self.assertEqual(response.data['user']['phone'], '9876543210')
        
        # Vérifier en base de données
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Updated Name')
        self.assertEqual(self.user.phone, '9876543210')
    
    def test_update_user_profile_unauthenticated(self):
        """Test de mise à jour du profil sans authentification."""
        update_data = {'name': 'Updated Name'}
        
        response = self.client.put('/api/users/update_profile/', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_user_profile_with_address(self):
        """Test de mise à jour du profil avec adresse."""
        self.authenticate_user(self.user_token)
        
        update_data = {
            'name': 'Updated Name',
            'address': {
                'street': '456 New Street',
                'city': 'New City',
                'postal_code': '54321',
                'country': 'New Country'
            }
        }
        
        response = self.client.put('/api/users/update_profile/', update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier en base de données
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Updated Name')
        self.assertIsNotNone(self.user.address)
        self.assertEqual(self.user.address.street, '456 New Street')
    
    def test_delete_user_profile_with_password(self):
        """Test de suppression du profil avec mot de passe correct."""
        self.authenticate_user(self.user_token)
        
        delete_data = {'password': 'testpassword123'}
        
        response = self.client.delete('/api/users/delete_me/', delete_data)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Vérifier que l'utilisateur a été supprimé
        self.assertFalse(User.objects.filter(email='test@example.com').exists())
    
    def test_delete_user_profile_wrong_password(self):
        """Test de suppression du profil avec mauvais mot de passe."""
        self.authenticate_user(self.user_token)
        
        delete_data = {'password': 'wrongpassword'}
        
        response = self.client.delete('/api/users/delete_me/', delete_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        # Vérifier que l'utilisateur n'a pas été supprimé
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
    
    def test_delete_user_profile_no_password(self):
        """Test de suppression du profil sans mot de passe."""
        self.authenticate_user(self.user_token)
        
        response = self.client.delete('/api/users/delete_me/', {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_delete_user_profile_unauthenticated(self):
        """Test de suppression du profil sans authentification."""
        delete_data = {'password': 'testpassword123'}
        
        response = self.client.delete('/api/users/delete_me/', delete_data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_admin_delete_profile(self):
        """Test de suppression de profil par un admin."""
        self.authenticate_user(self.admin_token)
        
        delete_data = {'email': 'test@example.com'}
        
        response = self.client.delete('/api/users/delete_profile/', delete_data)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Vérifier que l'utilisateur a été supprimé
        self.assertFalse(User.objects.filter(email='test@example.com').exists())
    
    def test_admin_delete_profile_user_not_found(self):
        """Test de suppression de profil inexistant par un admin."""
        self.authenticate_user(self.admin_token)
        
        delete_data = {'email': 'nonexistent@example.com'}
        
        response = self.client.delete('/api/users/delete_profile/', delete_data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_admin_delete_profile_no_email(self):
        """Test de suppression de profil sans email par un admin."""
        self.authenticate_user(self.admin_token)
        
        response = self.client.delete('/api/users/delete_profile/', {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_non_admin_delete_profile_forbidden(self):
        """Test de suppression de profil par un non-admin (interdit)."""

        self.assertFalse(self.user.is_superuser, "Test user should not be superuser")

        self.authenticate_user(self.user_token)
        
        delete_data = {'email': 'admin@example.com'}
        
        response = self.client.delete('/api/users/delete_profile/', delete_data)

        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print(f"User is_superuser: {self.user.is_superuser}")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserRegistrationWithAddressAPITests(APITestCase):
    """Tests fonctionnels spécifiques pour l'inscription avec adresse."""
    
    def setUp(self):
        """Configuration des données de test."""
        self.client = APIClient()
        
        self.complete_user_data = {
            'email': 'complete@example.com',
            'password': 'testpassword123',
            'name': 'Complete',
            'surname': 'User',
            'phone': '0123456789',
            'role': UserRole.CLIENT.value,
            'address': {
                'street': '789 Complete Street',
                'city': 'Complete City',
                'postal_code': '99999',
                'country': 'Complete Country'
            }
        }
    
    def test_user_registration_with_complete_address(self):
        """Test d'inscription avec adresse complète."""
        response = self.client.post('/api/users/register/', self.complete_user_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Vérifier que l'utilisateur et l'adresse ont été créés
        user = User.objects.get(email='complete@example.com')
        self.assertIsNotNone(user.address)
        self.assertEqual(user.address.street, '789 Complete Street')
        self.assertEqual(user.address.city, 'Complete City')
    
    def test_user_registration_with_incomplete_address(self):
        """Test d'inscription avec adresse incomplète."""
        incomplete_data = self.complete_user_data.copy()
        incomplete_data['address'] = {
            'street': '789 Incomplete Street',
            # city manquant
            'postal_code': '99999',
            'country': 'Incomplete Country'
        }
        
        response = self.client.post('/api/users/register/', incomplete_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('address', response.data)


# =============================================================================
# COMMANDES POUR EXÉCUTER LES TESTS
# =============================================================================
"""
Pour exécuter ces tests :

# Tous les tests
python manage.py test accounts.tests

# Tests unitaires seulement
python manage.py test accounts.tests.AddressModelTests
python manage.py test accounts.tests.UserModelTests
python manage.py test accounts.tests.AddressSerializerTests
python manage.py test accounts.tests.UserSerializerTests

# Tests fonctionnels seulement
python manage.py test accounts.tests.UserAPITests
python manage.py test accounts.tests.UserRegistrationWithAddressAPITests

# Avec coverage (si installé)
coverage run --source='.' manage.py test accounts.tests
coverage report
coverage html
"""