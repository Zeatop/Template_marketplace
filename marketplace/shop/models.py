from django.db import models
from colors import Colors
import datetime
from decimal import Decimal
from users.models import User
import requests
from stripe.models import StripeManager
from stripe.error import StripeError
from constants import STRIPE_ACCOUNT_ID
from rest_framework.response import Response
import logging
import json
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

class Product(models.Model):
    """Modèle représentant un produit."""
    
    name = models.CharField(max_length=255, verbose_name="Nom")
    description = models.TextField(verbose_name="Description")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    promotion_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix promotionnel", null=True, blank=True)
    image = models.ImageField(upload_to='products/', verbose_name="Image", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0, verbose_name="Stock")
    maxi_order_quantity = models.PositiveIntegerField(verbose_name="Quantité maximale par commande", default=9999)
    editor = models.CharField(max_length=255, verbose_name="Éditeur", null=True, blank=True)
    category = models.CharField(max_length=100, verbose_name="Catégorie", null=True, blank=True)
    release_date = models.DateField(verbose_name="Date de sortie", null=True, blank=True)
    preorder = models.BooleanField(default=False, verbose_name="Précommande")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    stripe_product_id = models.CharField(
        max_length=255, 
        verbose_name="ID Produit Stripe", 
        default=None,
    )  # ID Stripe pour la gestion des paiements

    class Meta:
        db_table = 'product'
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @classmethod
    def create_product(cls, product_infos: dict):
        """Crée un nouveau produit avec les informations fournies."""
        product = cls.objects.create(
            name=product_infos["name"], 
            description=product_infos["description"], 
            price=Decimal(product_infos["price"]),
            promotion_price=Decimal(product_infos.get("promotion_price", None)),
            stock=product_infos["stock"],
            maxi_order_quantity=product_infos["max_order_quantity"],
            category=product_infos.get("category", ""),
            image=product_infos.get("image", None),
            preorder=product_infos.get("preorder", False),
            release_date=product_infos.get("release_date", None),
            editor=product_infos.get("editor", "")
        )
        return product
    
    def sync_product_with_stripe(self):
        try:
            stripe_product = StripeManager.create_or_retrieve_product(
                name=self.name,
                description=self.description,
                stripe_account_id=STRIPE_ACCOUNT_ID,
            )
            self.stripe_product_id = stripe_product.id
            stripe_price = StripeManager.create_or_retrieve_price(
                product_id=stripe_product.id,
                unit_amount=int(self.price * 100),
                currency="eur",
                nickname="Standard Price",
                stripe_account_id=STRIPE_ACCOUNT_ID,
            )
            self.save()
            return stripe_product
        except StripeError as e:
            logger.error(f"Erreur Stripe pour produit {self.name}: {e}")
            return None        
        
        

    def get_user_cart(self):
        """Récupère le panier associé à l'utilisateur."""
        from marketplace.shop.models import Cart
        return Cart.objects.filter(user=self).first()
    
    def update_stock(self, stock):
        """Met à jour le stock du produit."""
        self.stock = stock
        self.save()
    
    def update_maxi_order_quantity(self, quantity):
        """Met à jour la quantité maximale par commande."""
        if quantity <= 0:
            raise ValueError("La quantité maximale doit être supérieure à zéro.")
        self.maxi_order_quantity = quantity
        self.save()
    
    def update_price(self, price):
        """Met à jour le prix du produit."""
        self.price = Decimal(price)
        self.save()
    
    def update_promotion_price(self, promotion_price):
        """Met à jour le prix promotionnel du produit."""
        if promotion_price:
            self.promotion_price = Decimal(promotion_price)
        else:
            self.promotion_price = None
        self.save()

    def update_image(self, image):
        """Met à jour l'image du produit."""
        if image:
            self.image = image
        else:
            self.image = None
        self.save()
    
    def update_editor(self, editor):
        """Met à jour l'éditeur du produit."""
        self.editor = editor
        self.save()
    
    def update_category(self, category):
        """Met à jour la catégorie du produit."""
        self.category = category
        self.save()
    
    def is_available(self):
        """Vérifie si le produit est disponible en stock."""
        return self.stock > 0
    
    def is_on_promotion(self):
        """Vérifie si le produit est en promotion."""
        return self.promotion_price is not None and self.promotion_price < self.price
    
    def update_release_date(self, release_date):
        """Met à jour la date de sortie du produit."""
        if release_date:
            self.release_date = release_date
        else:
            self.release_date = None
        self.save()
    
    def get_stock_status(self):
        """Retourne le statut du stock pour l'affichage."""
        if self.stock == 0:
            return "Rupture de stock"
        elif self.stock <= 5:
            return f"Plus que {self.stock} en stock"
        else:
            return "En stock"

    def get_max_purchasable_quantity(self):
        """Retourne la quantité maximale qu'on peut acheter."""
        if not self.is_available():
            return 0
        
        if self.maxi_order_quantity:
            return min(self.stock, self.maxi_order_quantity)
        return self.stock

    def can_purchase_quantity(self, quantity):
        """Vérifie si on peut acheter la quantité demandée."""
        if not self.is_available():
            return False, "Produit indisponible"
        
        if quantity > self.stock:
            return False, f"Stock insuffisant (disponible: {self.stock})"
        
        if self.maxi_order_quantity and quantity > self.maxi_order_quantity:
            return False, f"Quantité maximale: {self.maxi_order_quantity}"
        
        return True, "OK"

class CartItem(models.Model):
    """Modèle représentant un article dans le panier."""
    
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE, related_name='items', verbose_name="Panier")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name="Produit")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantité")
    
    class Meta:
        db_table = 'cart_item'
        verbose_name = 'Article de panier'
        verbose_name_plural = 'Articles de panier'
        unique_together = ('cart', 'product')
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} dans le panier {self.cart.id}"
    
    @property
    def total_price(self):
        """Calcule le prix total de l'article dans le panier."""
        if self.product.is_on_promotion():
            return self.quantity * self.product.promotion_price
        return self.quantity * self.product.price

class Cart(models.Model):
    """Modèle représentant un panier d'achat."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', verbose_name="Utilisateur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'cart'
        verbose_name = 'Panier'
        verbose_name_plural = 'Paniers'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Panier de {self.user.name} créé le {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def get_or_create_cart(cls, user: User):
        """Récupère ou crée le panier unique de l'utilisateur."""
        cart, created = cls.objects.get_or_create(user=user)
        return cart
    
    def add_product(self, product: Product, quantity: int):
        """Ajoute un produit au panier avec la quantité spécifiée."""
        if quantity <= 0:
            print(Colors.error("La quantité doit être supérieure à zéro."))
            return False
        
        cart_item, created = CartItem.objects.get_or_create(cart=self, product=product, defaults={'quantity': 0})
        new_quantity = cart_item.quantity + quantity

        # ✅ Utiliser la méthode utilitaire
        can_purchase, message = product.can_purchase_quantity(new_quantity)
        if not can_purchase:
            print(Colors.error(message))
            return False

        cart_item.quantity = new_quantity
        cart_item.save()
        
        print(Colors.success(f"{quantity} {product.name}(s) ajouté(s) au panier."))
        return True
    
    def update_product_quantity(self, product: Product, new_quantity: int):
        """Met à jour la quantité d'un produit dans le panier."""
        if new_quantity <= 0:
            return self.remove_product(product)
        
        # ✅ Utiliser la méthode utilitaire
        can_purchase, message = product.can_purchase_quantity(new_quantity)
        if not can_purchase:
            print(Colors.error(message))
            return False
        
        try:
            cart_item = CartItem.objects.get(cart=self, product=product)
            cart_item.quantity = new_quantity
            cart_item.save()
            print(Colors.success(f"Quantité mise à jour: {new_quantity} {product.name}(s)"))
            return True
        except CartItem.DoesNotExist:
            print(Colors.error(f"{product.name} n'est pas dans le panier."))
            return False

    @property
    def total_price(self):
        """Calcule le prix total de tous les articles dans le panier."""
        total_price = sum(item.total_price for item in self.items.all())
        return total_price

    @property
    def cart_items(self):
        """Récupère tous les articles du panier."""
        return self.items.all()

    @property
    def total_quantity(self):
        """Calcule la quantité totale de produits dans le panier."""
        total_quantity = sum(item.quantity for item in self.items.all())
        return total_quantity
    
    def remove_product(self, product: Product):
        """Supprime un produit du panier."""
        try:
            cart_item = CartItem.objects.get(cart=self, product=product)
            cart_item.delete()
            print(Colors.success(f"{product.name} supprimé du panier."))
        except CartItem.DoesNotExist:
            print(Colors.error(f"{product.name} n'est pas dans le panier."))
    
    def clear_cart(self):
        """Vide le panier de tous les produits."""
        CartItem.objects.filter(cart=self).delete()
        print(Colors.success("Le panier a été vidé."))
    
    def validate_cart(self):
        """Valide que tous les produits du panier sont encore disponibles."""
        invalid_items = []
        
        for item in self.items.all():
            can_purchase, message = item.product.can_purchase_quantity(item.quantity)
            if not can_purchase:
                invalid_items.append({
                    'item': item,
                    'error': message
                })
        
        return len(invalid_items) == 0, invalid_items

    def get_cart_summary(self):
        """Retourne un résumé du panier avec les statuts de stock."""
        summary = []
        for item in self.items.all():
            summary.append({
                'product': item.product.name,
                'quantity': item.quantity,
                'max_available': item.product.get_max_purchasable_quantity(),
                'stock_status': item.product.get_stock_status(),
                'total_price': item.total_price
            })
        return summary

    def fix_invalid_quantities(self):
        """Corrige automatiquement les quantités invalides dans le panier."""
        fixed_items = []
        
        for item in self.items.all():
            max_quantity = item.product.get_max_purchasable_quantity()
            if item.quantity > max_quantity:
                if max_quantity > 0:
                    item.quantity = max_quantity
                    item.save()
                    fixed_items.append(f"{item.product.name}: réduit à {max_quantity}")
                else:
                    item.delete()
                    fixed_items.append(f"{item.product.name}: supprimé (indisponible)")
        
        return fixed_items

class Order(models.Model):
    """Modèle représentant une commande.""" 

    SHIPMENT_TYPES = [
        ('standard', 'Standard'),
        ('express', 'Express'),
        ('pickup', 'Retrait en magasin'),
    ]

    SHIPMENT_STATUS = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
        ('disputed', 'Contestée')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Utilisateur")
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='orders', verbose_name="Panier")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix total")
    
    payment_intent_id = models.CharField(
        max_length=255,
        verbose_name="ID Payment Intent Stripe",
        null=True,
        blank=True,
        unique=True,  # Un Payment Intent = Une commande
        db_index=True  # Index pour recherche rapide dans webhooks
    )

    shipment_type = models.CharField(max_length=20, choices=SHIPMENT_TYPES, default='standard', verbose_name="Type d'expédition")
    delivery_address = models.CharField(max_length=255, verbose_name="Adresse de livraison", null=True, blank=True)
    billing_address = models.CharField(max_length=255, verbose_name="Adresse de facturation", null=True, blank=True)
    status = models.CharField(max_length=20, default='pending', verbose_name="Statut", choices=SHIPMENT_STATUS)
    tracking_number = models.CharField(max_length=50, verbose_name="Numéro de suivi", null=True, blank=True, default="Non défini")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'order'
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['payment_intent_id', 'status']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Commande {self.id} de {self.user.name} - Total: {self.total_price} €"
    
    @classmethod
    def create_order(cls, user: User, cart: Cart):
        """Crée une nouvelle commande à partir du panier de l'utilisateur."""
        if not cart.items.exists():
            return None, ["Le panier est vide."]
        
        is_valid, invalid_items = cart.validate_cart()
        if not is_valid:
            errors = []
            print(Colors.error("Impossible de créer la commande :"))
            for invalid in invalid_items:
                product_name = invalid['item'].product.name
                error_msg = invalid['error']
                errors.append(f"Cet article n'est plus en stock : {product_name} - {error_msg}")
            return None, errors
        
        from django.db import transaction
        try:
            with transaction.atomic():
                # ✅ Utiliser les méthodes utilitaires
                for item in cart.items.all():
                    product = Product.objects.select_for_update().get(id=item.product.id)
                    can_purchase, message = product.can_purchase_quantity(item.quantity)
                    if not can_purchase:
                        return None, [f"Cet article n'est plus en stock : {product.name} - {message}"]
                
                # Si tout est OK, créer la commande
                total_price = cart.total_price
                order = cls.objects.create(user=user, cart=cart, total_price=total_price)
                payment_intent = StripeManager.create_payment_intent_for_order(
                    customer_id=user.stripe_user_id,
                    amount=int(total_price * 100),  # En centimes
                    order_id=order.id,
                    stripe_account_id=STRIPE_ACCOUNT_ID
                )
                
                if not payment_intent:
                    # Si échec Payment Intent, annuler la commande
                    raise Exception("Échec création Payment Intent")
                
                # 🔑 CRUCIAL : Sauvegarder l'ID Payment Intent
                order.payment_intent_id = payment_intent.id
                order.save()

                # 🆕 Créer les OrderItems (snapshot figé)
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        product_name=cart_item.product.name,  # Figer le nom
                        quantity=cart_item.quantity,
                        unit_price=cart_item.product.promotion_price if cart_item.product.is_on_promotion() 
                                else cart_item.product.price  # Figer le prix
                    )
                
                # Réduire le stock de tous les produits
                for item in cart.items.all():
                    product = Product.objects.select_for_update().get(id=item.product.id)
                    product.stock -= item.quantity
                    product.save()
                
                cart.clear_cart()
                print(Colors.success(f"Commande {order.id} créée avec succès."))
                return order, []
            
        except Exception as e:
            return None, [f"Erreur lors de la création de la commande : {str(e)}"]
        
    def set_tracking_number(self, tracking_number: str):
        """Définit le numéro de suivi de la commande."""
        self.tracking_number = tracking_number
        self.save()
    
    @classmethod
    def get_by_payment_intent(cls, payment_intent_id):
        """Récupère une commande par son Payment Intent ID."""
        try:
            return cls.objects.get(payment_intent_id=payment_intent_id)
        except cls.DoesNotExist:
            return None

    @property
    def order_items(self):
        """Récupère les articles de la commande."""
        return self.items.all()
    
    def get_shipment_type_display(self):
        """Renvoie une représentation lisible du type d'expédition."""
        return dict(self.SHIPMENT_TYPES).get(self.shipment_type, 'Inconnu')
    
    def get_status_display(self):
        """Renvoie une représentation lisible du statut de la commande."""
        return dict(self.SHIPMENT_STATUS).get(self.status, 'Inconnu')
    
    def get_delivery_address(self):
        """Renvoie l'adresse de livraison de la commande."""
        return self.delivery_address if self.delivery_address else "Aucune adresse de livraison spécifiée"
    
    def get_billing_address(self):
        """Renvoie l'adresse de facturation de la commande."""
        return self.billing_address if self.billing_address else "Aucune adresse de facturation spécifiée"
    
    def get_order_summary(self):
        """Renvoie un résumé de la commande."""
        items_summary = "\n".join([f"{item.quantity} x {item.product_name} - {item.total_price} €" for item in self.order_items])
        return (
            f"Commande ID: {self.id}\n"
            f"Utilisateur: {self.user.name}\n"
            f"Total: {self.total_price} €\n"
            f"Type d'expédition: {self.get_shipment_type_display()}\n"
            f"Statut: {self.get_status_display()}\n"
            f"Adresse de livraison: {self.get_delivery_address()}\n"
            f"Adresse de facturation: {self.get_billing_address()}\n"
            f"Articles:\n{items_summary}"
        )
    
    def cancel_order(self):
        """Annule la commande si elle est en attente ou en cours de traitement."""
        if self.status in ['pending', 'processing']:
            from django.db import transaction
            
            with transaction.atomic():
                # Remettre le stock en place
                for order_item in self.items.all():
                    product = order_item.product
                    product.stock += order_item.quantity
                    product.save()
                
                self.status = 'cancelled'
                self.save()
                
            print(Colors.success(f"La commande {self.id} a été annulée et le stock a été remis en place."))
            return True
        else:
            print(Colors.error(f"La commande {self.id} ne peut pas être annulée car son statut est {self.get_status_display()}."))
            return False
    
    def confirm_order(self):
        """Confirme la commande si elle est en attente."""
        if self.status == 'pending':
            self.status = 'processing'
            self.save()
            print(Colors.success(f"La commande {self.id} a été confirmée et est en cours de traitement."))
        else:
            print(Colors.error(f"La commande {self.id} ne peut pas être confirmée car son statut est {self.get_status_display()}."))
    
    def update_status(self, status: str):
        """Met manuellement à jour le statut de la commande."""
        if status in dict(self.SHIPMENT_STATUS):
            self.status = status
            self.save()
    
    def check_delivery_status(self):
        """Vérifie automatiquement le statut de livraison via l'API du transporteur."""
        if not self.tracking_number:
            return None
        
        try:
            delivery_status = self._get_carrier_status()
            if delivery_status:
                mapped_status = self._map_carrier_status_to_order_status(delivery_status)
                if mapped_status and mapped_status != self.status:
                    self.status = mapped_status
                    self.save()
                    print(Colors.success(f"Statut de la commande {self.id} mis à jour: {self.get_status_display()}"))
                return delivery_status
        except Exception as e:
            print(Colors.error(f"Erreur lors de la vérification du statut: {e}"))
        return None
    
    def _get_carrier_status(self):
        """Récupère le statut depuis l'API du transporteur selon le type d'expédition."""
        
        if self.shipment_type == 'standard':
            # API Colissimo/La Poste
            url = f"https://api.laposte.fr/suivi/v2/idships/{self.tracking_number}"
            headers = {"X-Okapi-Key": "YOUR_API_KEY"}  # À remplacer par votre clé API
        elif self.shipment_type == 'express':
            # API Chronopost
            url = f"https://www.chronopost.fr/tracking-cxf/TrackingServiceWS/track"
            # Implémentation spécifique à Chronopost
        else:
            return None
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get('status') or data.get('eventCode')
        except requests.RequestException:
            pass
        return None
    
    def _map_carrier_status_to_order_status(self, carrier_status):
        """Mappe le statut du transporteur vers le statut de commande."""
        status_mapping = {
            # Colissimo/La Poste
            'PC1': 'processing',  # Pris en charge
            'ET1': 'shipped',     # En transit
            'DI1': 'delivered',   # Distribué
            # Chronopost
            'SENT': 'shipped',
            'DELIVERED': 'delivered',
            'IN_TRANSIT': 'shipped',
        }
        return status_mapping.get(carrier_status)
    
class OrderItem(models.Model):
    """Modèle représentant un article dans une commande (snapshot figé)."""
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='items', verbose_name="Commande")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produit")
    product_name = models.CharField(max_length=255, verbose_name="Nom du produit (figé)")
    quantity = models.PositiveIntegerField(verbose_name="Quantité")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix unitaire (figé)")
    
    class Meta:
        db_table = 'order_item'
        verbose_name = 'Article de commande'
        verbose_name_plural = 'Articles de commande'
        unique_together = ('order', 'product')
    
    def __str__(self):
        return f"{self.quantity} x {self.product_name} dans commande {self.order.id}"
    
    @property
    def total_price(self):
        """Prix total de cette ligne de commande."""
        return self.quantity * self.unit_price
    
class WebhookEvent(models.Model):
    """Modèle pour traquer les événements webhook Stripe et assurer l'idempotence."""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('success', 'Traité avec succès'),
        ('failed', 'Échec'),
        ('retry', 'En attente de retry'),
        ('max_retries_exceeded', 'Nombre max de tentatives dépassé'),
    ]
    
    # Identifiants Stripe
    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="ID Événement Stripe"
    )
    
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Type d'événement"
    )
    
    # Contenu de l'événement
    event_data = models.JSONField(
        verbose_name="Données de l'événement",
        help_text="Contenu complet de l'événement Stripe"
    )
    
    # Statut du traitement
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name="Statut de traitement"
    )
    
    # Gestion des retries
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de tentatives"
    )
    
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name="Nombre maximum de tentatives"
    )
    
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Prochaine tentative à"
    )
    
    # Logs et erreurs
    processing_logs = models.JSONField(
        default=list,
        verbose_name="Logs de traitement"
    )
    
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Message d'erreur"
    )
    
    # Métadonnées
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Traité le"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Reçu le"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Modifié le"
    )

    class Meta:
        db_table = 'webhook_event'
        verbose_name = 'Événement Webhook'
        verbose_name_plural = 'Événements Webhook'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_event_id']),
            models.Index(fields=['event_type', 'status']),
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Webhook {self.event_type} - {self.stripe_event_id} ({self.status})"

    @classmethod
    def is_already_processed(cls, stripe_event_id):
        """Vérifie si un événement a déjà été traité (idempotence)."""
        return cls.objects.filter(
            stripe_event_id=stripe_event_id,
            status__in=['success', 'max_retries_exceeded']
        ).exists()

    @classmethod
    def create_from_stripe_event(cls, stripe_event):
        """Crée un WebhookEvent à partir d'un événement Stripe."""
        webhook_event, created = cls.objects.get_or_create(
            stripe_event_id=stripe_event['id'],
            defaults={
                'event_type': stripe_event['type'],
                'event_data': stripe_event,
                'status': 'pending'
            }
        )
        return webhook_event, created

    def add_log(self, message, level='info'):
        """Ajoute un log de traitement."""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'level': level,
            'message': message,
            'retry_count': self.retry_count
        }
        
        if not isinstance(self.processing_logs, list):
            self.processing_logs = []
            
        self.processing_logs.append(log_entry)
        self.save(update_fields=['processing_logs', 'updated_at'])

    def mark_as_processing(self):
        """Marque l'événement comme en cours de traitement."""
        self.status = 'processing'
        self.add_log("Début du traitement de l'événement")
        self.save(update_fields=['status', 'updated_at'])

    def mark_as_success(self, message="Traitement réussi"):
        """Marque l'événement comme traité avec succès."""
        self.status = 'success'
        self.processed_at = timezone.now()
        self.error_message = None
        self.add_log(message, 'success')
        self.save(update_fields=['status', 'processed_at', 'error_message', 'updated_at'])

    def mark_as_failed(self, error_message, should_retry=True):
        """Marque l'événement comme échoué et programme un retry si nécessaire."""
        self.error_message = error_message
        self.add_log(f"Échec: {error_message}", 'error')
        
        if should_retry and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = 'retry'
            
            # Backoff exponentiel : 2^retry_count minutes
            delay_minutes = 2 ** self.retry_count
            self.next_retry_at = timezone.now() + timedelta(minutes=delay_minutes)
            
            self.add_log(f"Programmation retry #{self.retry_count} dans {delay_minutes} minutes")
            
        else:
            self.status = 'max_retries_exceeded'
            self.add_log("Nombre maximum de tentatives atteint", 'error')
        
        self.save(update_fields=[
            'status', 'retry_count', 'next_retry_at', 
            'error_message', 'updated_at'
        ])

    def can_retry(self):
        """Vérifie si l'événement peut être retrié."""
        return (
            self.status == 'retry' and
            self.next_retry_at and
            timezone.now() >= self.next_retry_at
        )

    @classmethod
    def get_events_to_retry(cls):
        """Récupère les événements prêts à être retriés."""
        return cls.objects.filter(
            status='retry',
            next_retry_at__lte=timezone.now()
        ).order_by('next_retry_at')

    @classmethod
    def cleanup_old_events(cls, days=30):
        """Nettoie les anciens événements (à exécuter périodiquement)."""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = cls.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['success', 'max_retries_exceeded']
        ).delete()[0]
        return deleted_count