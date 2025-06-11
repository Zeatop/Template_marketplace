from django.db import models
from enum import Enum, auto
import bcrypt

class Permissions(Enum):
    """Définit les niveaux de permission dans l'application."""
    MANAGEMENT_TEAM = auto()
    LOGISTIC_TEAM = auto()
    COMMERCIAL_TEAM = auto()

class UserRole(Enum):
    """Définit les rôles utilisateur disponibles."""
    SUPPORT = "support"
    COMMERCIAL = "commercial"
    MANAGEMENT = "Management"

class Security:
    """Gère les fonctionnalités de sécurité liées aux mots de passe."""
    
    @staticmethod
    def hash_password(password):
        """Crée une version hashée du mot de passe fourni."""
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')

    @staticmethod
    def verify_password(password, hashed_password):
        """Vérifie si le mot de passe correspond au hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

class User(models.Model):
    """Modèle représentant un utilisateur du CRM."""
    
    ROLE_CHOICES = [
        (UserRole.SUPPORT.value, 'Support'),
        (UserRole.COMMERCIAL.value, 'Commercial'),
        (UserRole.MANAGEMENT.value, 'Management'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="Nom")
    mail = models.EmailField(unique=True, verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    password = models.CharField(max_length=255, verbose_name="Mot de passe")
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        verbose_name="Rôle"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'user'
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['name']
    
    def __str__(self):
        return self.name

    @property
    def get_permission(self):
        """Renvoie les permissions associées au rôle de l'utilisateur."""
        role_permissions = {
            UserRole.SUPPORT.value: Permissions.LOGISTIC_TEAM,
            UserRole.COMMERCIAL.value: Permissions.COMMERCIAL_TEAM,
            UserRole.MANAGEMENT.value: Permissions.MANAGEMENT_TEAM,
        }
        return role_permissions.get(self.role)
        
    @classmethod
    def create_user(cls, account_infos: dict):
        """Crée un nouvel utilisateur avec les informations fournies."""
        hashed_password = Security.hash_password(account_infos["password"])
        user = cls.objects.create(
            name=account_infos["name"], 
            mail=account_infos["mail"],
            phone=account_infos["phone"], 
            password=hashed_password,
            role=account_infos["role"]
        )
        return user
    
    def check_password(self, password):
        """Vérifie si le mot de passe fourni correspond à celui de l'utilisateur."""
        return Security.verify_password(password, self.password)
    
    def set_password(self, password):
        """Définit un nouveau mot de passe pour l'utilisateur."""
        self.password = Security.hash_password(password)
        self.save()
    
    def is_management(self):
        """Vérifie si l'utilisateur fait partie de l'équipe de management."""
        return self.role == UserRole.MANAGEMENT.value
    
    def is_commercial(self):
        """Vérifie si l'utilisateur fait partie de l'équipe commerciale."""
        return self.role == UserRole.COMMERCIAL.value
    
    def is_support(self):
        """Vérifie si l'utilisateur fait partie de l'équipe support."""
        return self.role == UserRole.SUPPORT.value