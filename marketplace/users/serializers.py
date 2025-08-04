from .models import User, Address, UserRole
from rest_framework import serializers
from django.contrib.auth import get_user_model

class AddressSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Address."""
    
    class Meta:
        model = Address
        fields = ['street', 'city', 'postal_code', 'country']
    
    def validate(self, data):
        """Valide les données de l'adresse."""
        if not data.get('street'):
            raise serializers.ValidationError("Street is required.")
        if not data.get('city'):
            raise serializers.ValidationError("City is required.")
        if not data.get('postal_code'):
            raise serializers.ValidationError("Postal code is required.")
        if not data.get('country'):
            raise serializers.ValidationError("Country is required.")
        return data
    

class UserSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle User avec AbstractUser."""
    
    name = serializers.CharField(max_length=255, required=True)
    surname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=True)  # ✅ email maintenant
    phone = serializers.CharField(max_length=20, required=True, allow_blank=False)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    
    # ✅ Nested serializer pour Address
    address = AddressSerializer(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'surname', 'email', 'phone', 'password', 
            'role', 'address', 'date_joined', 'stripe_user_id',
        ]
        read_only_fields = ['id', 'date_joined', 'stripe_user_id']

    def validate_email(self, value):
        """Valide l'unicité de l'email."""
        if not self.instance:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        else:
            # Pour une mise à jour (instance existe)
            if User.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        return value
    
    def validate_password(self, value):
        """Valide la complexité du mot de passe."""
        if len(value) < 8:
            raise serializers.ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
        return value

    def create(self, validated_data):
        """Crée un nouvel utilisateur."""
        # ✅ Structure adaptée pour create_user
        account_infos = {
            'email': validated_data['email'],
            'password': validated_data['password'],
            'name': validated_data.get('name', ''),
            'surname': validated_data.get('surname', ''),
            'phone': validated_data.get('phone', ''),
            'role': validated_data.get('role', UserRole.CLIENT.value),
            'address': validated_data.get('address'),
            'stripe_user_id': validated_data.get('stripe_user_id', None),
        }
        
        user = User.create_user(account_infos)
        return user

    def update(self, instance, validated_data):
        """Met à jour un utilisateur existant."""
        # Gestion de l'adresse
        address_data = validated_data.pop('address', None)
        
        # Mise à jour des champs
        instance.name = validated_data.get('name', instance.name)
        instance.surname = validated_data.get('surname', instance.surname)
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.role = validated_data.get('role', instance.role)
        
        # ✅ Utilisation de set_password d'AbstractUser
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])
        
        # Gestion de l'adresse
        if address_data is not None:
            if instance.address:
                address_serializer = AddressSerializer(instance.address, data=address_data)
                if address_serializer.is_valid():
                    address_serializer.save()
            else:
                address_serializer = AddressSerializer(data=address_data)
                if address_serializer.is_valid():
                    instance.address = address_serializer.save()
        
        instance.save()
        return instance