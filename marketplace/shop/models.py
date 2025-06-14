from django.db import models
from colors import Colors
import datetime
from decimal import Decimal
from users.models import User
import requests

class Product(models.Model):
    """Modèle représentant un produit."""
    
    name = models.CharField(max_length=255, verbose_name="Nom")
    description = models.TextField(verbose_name="Description")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    promotion_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix promotionnel", null=True, blank=True)
    image = models.ImageField(upload_to='products/', verbose_name="Image", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0, verbose_name="Stock")
    editor = models.CharField(max_length=255, verbose_name="Éditeur", null=True, blank=True)
    category = models.CharField(max_length=100, verbose_name="Catégorie", null=True, blank=True)
    release_date = models.DateField(verbose_name="Date de sortie", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

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
            price=Decimal(product_infos["price"])
        )
        return product
    
    def update_stock(self, stock):
        """Met à jour le stock du produit."""
        self.stock = stock
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
    
    def get_total_price(self):
        """Calcule le prix total de l'article dans le panier."""
        if self.product.is_on_promotion():
            return self.quantity * self.product.promotion_price
        return self.quantity * self.product.price

class Cart(models.Model):
    """Modèle représentant un panier d'achat."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts', verbose_name="Utilisateur")
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
    def create_cart(cls, user: User):
        """Crée un nouveau panier pour l'utilisateur."""
        cart = cls.objects.create(user=user)
        return cart
    
    def add_product(self, product: Product, quantity: int):
        """Ajoute un produit au panier avec la quantité spécifiée."""
        if quantity <= 0:
            print(Colors.error("La quantité doit être supérieure à zéro."))
            return
        
        cart_item, created = CartItem.objects.get_or_create(cart=self, product=product)
        cart_item.quantity += quantity
        cart_item.save()
        
        print(Colors.success(f"{quantity} {product.name}(s) ajouté(s) au panier."))
    
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
        ('cancelled', 'Annulée')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Utilisateur")
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='orders', verbose_name="Panier")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix total")
    shipment_type = models.CharField(max_length=20, choices=SHIPMENT_TYPES, default='standard', verbose_name="Type d'expédition")
    delivery_address = models.CharField(max_length=255, verbose_name="Adresse de livraison", null=True, blank=True)
    billing_address = models.CharField(max_length=255, verbose_name="Adresse de facturation", null=True, blank=True)
    status = models.CharField(max_length=20, default='pending', verbose_name="Statut", choices=SHIPMENT_STATUS)
    tracking_number = models.CharField(max_length=50, verbose_name="Numéro de suivi", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'order'
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Commande {self.id} de {self.user.name} - Total: {self.total_price} €"
    
    @classmethod
    def create_order(cls, user: User, cart: Cart):
        """Crée une nouvelle commande à partir du panier de l'utilisateur."""
        total_price = sum(item.get_total_price() for item in cart.items.all())
        order = cls.objects.create(user=user, cart=cart, total_price=total_price)
        return order
    
    def set_tracking_number(self, tracking_number: str):
        """Définit le numéro de suivi de la commande."""
        self.tracking_number = tracking_number
        self.save()
    
    def get_order_items(self):
        """Récupère les articles de la commande."""
        return self.cart.items.all()
    
    def get_total_price(self):
        """Calcule le prix total de la commande."""
        return sum(item.get_total_price() for item in self.get_order_items())
    
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
        items_summary = "\n".join([f"{item.quantity} x {item.product.name} - {item.get_total_price()} €" for item in self.get_order_items()])
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
            self.status = 'cancelled'
            self.save()
            print(Colors.success(f"La commande {self.id} a été annulée."))
        else:
            print(Colors.error(f"La commande {self.id} ne peut pas être annulée car son statut est {self.get_status_display()}."))
    
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