from django.utils import timezone
from .models import Product, CartItem, Cart, Order
from rest_framework import serializers
from users.serializers import UserSerializer


class ProductSerializer(serializers.ModelSerializer):

    """Serializer pour le modèle Product."""

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'promotion_price',
            'stock', 'maxi_order_quantity', 'category', 'image',
            'preorder', 'release_date', 'editor', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        """Valide le nom du produit."""
        if not self.instance:
            if Product.objects.filter(name=value).exists():
                raise serializers.ValidationError("Un produit avec cet name existe déjà.")
        else:
            # Pour une mise à jour (instance existe)
            if Product.objects.filter(name=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Un produit avec cet name existe déjà.")
        return value
    
    def validate_price(self, value):
        """Valide le prix."""
        if value <= 0:
            raise serializers.ValidationError("Le prix doit être supérieur à 0.")
        return value
    
    def validate_promotion_price(self, value):
        if value and value <= 0:
            raise serializers.ValidationError("Le prix promotionnel doit être positif.")
        return value
        
    def validate_stock(self, value):
        """Valide le stock."""
        if value < 0:
            raise serializers.ValidationError("Le stock ne peut pas être négatif.")
        return value
    
    def validate_release_date(self, value):
        """Valide la date de sortie."""
        if value and value < timezone.now().date():
            raise serializers.ValidationError("La date de sortie ne peut pas être dans le passé.")
        return value
    
    def validate(self, data):
        """Validation entre plusieurs champs."""
        price = data.get('price')
        promotion_price = data.get('promotion_price')
        
        if promotion_price and price and promotion_price >= price:
            raise serializers.ValidationError(
                "Le prix promotionnel doit être inférieur au prix normal."
            )
        return data


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle CartItem."""

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'cart', 'total_price']
        read_only_fields = ['id', 'cart', 'total_price']

    def validate_quantity(self, value):
        """Valide la quantité."""
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être supérieure à 0.")
        return value
    
    def validate(self, data):
        """Validation complète avec instance."""
        product = data.get('product') or (self.instance.product if self.instance else None)
        quantity = data.get('quantity') or (self.instance.quantity if self.instance else 0)
        
        if product:
            can_purchase, message = product.can_purchase_quantity(quantity)
            if not can_purchase:
                raise serializers.ValidationError(message)
        
        return data


class CartSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Cart."""

    items = CartItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_price', 'total_quantity', 'created_at']
        read_only_fields = ['id', 'user', 'total_price', 'total_quantity' ,'created_at']


class OrderSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Order."""

    user = UserSerializer(read_only=True)
    cart = CartSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'cart', 'total_price', 'shipment_type',
            'delivery_address', 'billing_address', 'tracking_number',
            'order_items', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'cart', 'order_items', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Crée une commande en utilisant la méthode du modèle."""
        user = self.context['request'].user  # Récupérer l'utilisateur du context
        cart = user.carts.last()  # Ou une autre logique pour récupérer le bon panier
        
        # Utiliser la méthode create_order du modèle
        order, errors = Order.create_order(user=user, cart=cart)
        
        if not order:
            error_message = "Impossible de créer la commande :\n" + "\n".join(errors)
            raise serializers.ValidationError(error_message)
        
        # Mettre à jour les champs modifiables
        for field in ['shipment_type', 'delivery_address', 'billing_address']:
            if field in validated_data:
                setattr(order, field, validated_data[field])
        
        order.save()
        return order
    
    def validate_shipment_type(self, value):
        """Valide le type d'expédition."""
        valid_types = [choice[0] for choice in Order.SHIPMENT_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Type d'expédition invalide. Choix : {valid_types}")
        return value