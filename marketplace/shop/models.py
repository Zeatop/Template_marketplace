from django.db import models
from colors import Colors
import datetime
from decimal import Decimal
from users.models import User

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
    product = models.ForeignKey(product, on_delete=models.CASCADE, related_name='cart_items', verbose_name="Produit")
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
    
    def add_product(self, product: product, quantity: int):
        """Ajoute un produit au panier avec la quantité spécifiée."""
        if quantity <= 0:
            print(Colors.error("La quantité doit être supérieure à zéro."))
            return
        
        cart_item, created = CartItem.objects.get_or_create(cart=self, product=product)
        cart_item.quantity += quantity
        cart_item.save()
        
        print(Colors.success(f"{quantity} {product.name}(s) ajouté(s) au panier."))
    
    def remove_product(self, product: product):
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
    