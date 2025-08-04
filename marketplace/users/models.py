from django.db import models
from enum import Enum, auto
from django.contrib.auth.models import AbstractUser
from rest_framework.response import Response
from stripe.models import StripeManager
from stripe.error import StripeError
from constants import STRIPE_ACCOUNT_ID  # Importer l'ID du compte Stripe

class Permissions(Enum):
    """Définit les niveaux de permission dans l'application."""
    WORKER = auto()
    ADMIN = auto()
    CLIENT = auto()

class UserRole(Enum):
    """Définit les rôles utilisateur disponibles."""
    WORKER = "Worker"
    ADMIN = "Admin"
    CLIENT = "Client"

class Address(models.Model):
    """Modèle représentant une adresse associée à un utilisateur."""
    
    street = models.CharField(max_length=255, verbose_name="Rue")
    city = models.CharField(max_length=100, verbose_name="Ville")
    postal_code = models.CharField(max_length=20, verbose_name="Code Postal")
    country = models.CharField(max_length=100, verbose_name="Pays")
    
    class Meta:
        db_table = 'address'
        verbose_name = 'Adresse'
        verbose_name_plural = 'Adresses'
    
    def __str__(self):
        return f"{self.street}, {self.city}, {self.postal_code}, {self.country}"

class User(AbstractUser):
    """Modèle utilisateur personnalisé héritant d'AbstractUser."""
    
    ROLE_CHOICES = [
        (UserRole.WORKER.value, 'Worker'),
        (UserRole.ADMIN.value, 'Admin'),
        (UserRole.CLIENT.value, 'Client'),
    ]
    
    email = models.EmailField(unique=True, verbose_name="Email")
    name = models.CharField(max_length=255, verbose_name="Nom", blank=True)
    surname = models.CharField(max_length=255, verbose_name="Prénom", null=True, blank=True)
    phone = models.CharField(max_length=20, verbose_name="Téléphone", blank=True)
    stripe_user_id = models.CharField(
        max_length=255, 
        verbose_name="ID Client Stripe", 
        null=True, 
        blank=True, 
        default=None
    )  # ✅ ID Stripe pour la gestion des paiements
    address = models.ForeignKey(
        Address, 
        on_delete=models.CASCADE,
        related_name='users', 
        verbose_name="Adresse", 
        null=True, 
        blank=True
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        verbose_name="Rôle",
        default=UserRole.CLIENT.value  # ✅ Rôle par défaut
    )
    
    # ✅ AbstractUser a déjà date_joined, mais on peut ajouter updated_at
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    # ✅ Configuration pour l'authentification
    USERNAME_FIELD = 'email'  # Utiliser email au lieu de username
    REQUIRED_FIELDS = ['name']  # Champs requis lors de createsuperuser

    class Meta:
        db_table = 'user'
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['name']
    
    def __str__(self):
        return self.email

    @property
    def get_permission(self):
        """Renvoie les permissions associées au rôle de l'utilisateur."""
        role_permissions = {
            UserRole.WORKER.value: Permissions.WORKER,  # ✅ Plus logique
            UserRole.ADMIN.value: Permissions.ADMIN,  # ✅ Plus logique
            UserRole.CLIENT.value: Permissions.CLIENT,  # ✅ Plus logique
        }
        return role_permissions.get(self.role)
        
    @classmethod
    def create_user(cls, account_infos: dict):
        """Crée un nouvel utilisateur avec les informations fournies."""

        address_data = account_infos.pop("address", None)
        
        # Créer l'adresse si fournie
        address = None
        if address_data:
            address = Address.objects.create(**address_data)
        
        is_staff = False
        is_superuser = False
        role = account_infos.get("role", UserRole.CLIENT.value)
        if role == UserRole.ADMIN.value:
            is_staff = True
            is_superuser = True
        elif role == UserRole.WORKER.value:
            is_staff = True


        
        # ✅ Utiliser create_user d'AbstractUser
        user = cls.objects.create_user(
            username=account_infos["email"],
            email=account_infos["email"],  # ✅ email au lieu de mail
            password=account_infos["password"],  # ✅ Hashage automatique
            name=account_infos.get("name", ""),
            surname=account_infos.get("surname", ""),
            phone=account_infos.get("phone", ""),
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser,
            address=address,
        )
        return user    

    def sync_user_with_stripe(self):
        try:
            stripe_customer = StripeManager.create_or_retrieve_customer(
                email=self.email,
                name=self.name,
                stripe_account_id=STRIPE_ACCOUNT_ID,
            )
        except StripeError:
            return Response({'error': 'Erreur lors de la création du compte de paiement'})
        self.stripe_user_id = stripe_customer.id
        self.save()
        return stripe_customer
        

    def get_user_cart(self):
        """Récupère le panier associé à l'utilisateur."""
        from marketplace.shop.models import Cart
        return Cart.objects.filter(user=self).first()
    
    def has_admin_access(self):
        """Vérifie si l'utilisateur a les droits admin."""
        return self.is_superuser
    
    def has_staff_access(self):
        """Vérifie si l'utilisateur a les droits staff."""
        return self.is_staff

    def is_admin(self):
        """Vérifie si l'utilisateur est administrateur."""
        return self.role == UserRole.ADMIN.value
    
    def is_worker(self):
        """Vérifie si l'utilisateur est un worker."""
        return self.role == UserRole.WORKER.value
    
    def is_client(self):
        """Vérifie si l'utilisateur est un client."""
        return self.role == UserRole.CLIENT.value