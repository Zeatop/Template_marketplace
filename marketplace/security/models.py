from django.db import models
import bcrypt
import datetime
import jwt
import os
from colors import Colors
from users.models import User

SECRET_KEY = "clé_secrète"

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

class Token:
    """Gère la création et validation des tokens d'authentification."""

    @classmethod
    def generate_token(cls, mail):
        """Génère un token JWT pour l'utilisateur identifié par email."""
        expiration = datetime.datetime.now() + datetime.timedelta(days=1)
        payload = {
            "mail": mail,
            "exp": expiration.timestamp()
        }
        encoded_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        return encoded_token
    
    @staticmethod
    def store_token(token):
        """Stocke le token localement dans un fichier."""
        with open('.token', 'w') as f:
            f.write(f'{token}')
        
    @staticmethod
    def get_local_token():
        """Récupère le token stocké localement."""
        try:
            with open('.token', 'r') as f:
                token = f.read()
                return token
        except Exception as e:
            print(f"Token non trouvé en local : {e}")
            return None

    @staticmethod
    def decode_token(token, secret_key):
        """Décode un token JWT et le retourne."""
        try:
            decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return decoded_payload
        except jwt.ExpiredSignatureError:
            print(Colors.info('Le token a expiré'))
            return None
        except jwt.InvalidTokenError:
            print(Colors.error('Token non valide'))
            return None

    @classmethod
    def is_valid(cls, payload):
        """Vérifie si le token est valide et non expiré."""
        try:
            expiration = payload['exp']
            current_timestamp = datetime.datetime.now().timestamp()
            return current_timestamp < expiration
        except (KeyError, TypeError):
            return False

    @staticmethod
    def get_permissions(payload):
        """Récupère les permissions de l'utilisateur à partir du payload."""
        try:
            user = User.objects.get(mail=payload["mail"])
            return user.role
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def delete_local_token():
        """Supprime le token stocké localement."""
        try:
            os.remove('.token')
            print(Colors.info("Token local supprimé."))
        except FileNotFoundError:
            print(Colors.info("Aucun token local à supprimer."))
        except Exception as e:
            print(Colors.error(f"Erreur lors de la suppression du token local : {e}"))