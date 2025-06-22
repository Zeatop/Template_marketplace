from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .filters import ProductFilter
from .permissions import IsSuperUser
from .models import Product, Cart, Order
from .serializers import ProductSerializer, CartSerializer, OrderSerializer
from django.contrib.auth import get_user_model
from django.db import transaction


User = get_user_model()


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des produits."""
    
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'name' 

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'editor']
    ordering_fields = ['price', 'created_at', 'release_date', 'name']
    ordering = ['name']

    def get_object(self):

        """Override pour gérer les caractères spéciaux dans les noms."""

        from urllib.parse import unquote
        
        # 1️⃣ Récupère la valeur depuis l'URL
        encoded_name = self.kwargs.get('name', '')  # "iPhone%2015%20Pro"
        
        # 2️⃣ Décode l'URL 
        name = unquote(encoded_name)  # "iPhone 15 Pro"
        
        # 3️⃣ Recherche en base avec le nom décodé
        try:
            return Product.objects.get(name=name)
        except Product.DoesNotExist:
            from django.http import Http404
            raise Http404("Produit non trouvé")

    def get_permissions(self):
        """Définit les permissions selon l'action."""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action in ['low_stock', 'create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def promotions(self, request):
        """Récupère tous les produits en promotion."""
        from django.db.models import F
        products = self.get_queryset().filter(
            promotion_price__isnull=False,
            promotion_price__lt=F('price')
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def categories(self, request):
        """Liste toutes les catégories disponibles."""
        categories = Product.objects.values_list('category', flat=True).distinct()
        categories = [cat for cat in categories if cat]  # Supprimer les None
        return Response({'categories': categories})
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def low_stock(self, request):
        """Produits avec stock faible (≤ 5)."""
        products = self.get_queryset().filter(stock__lte=5, stock__gt=0)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    

class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des commandes."""
    
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'shipment_type', 'created_at']
    ordering_fields = ['created_at', 'total_price', 'status']
    ordering = ['-created_at']  # Plus récentes en premier
    
    def get_queryset(self):
        """Filtre les commandes selon les permissions."""
        if self.request.user.is_staff:
            # Admin voit toutes les commandes
            return Order.objects.all()
        else:
            # Utilisateur voit ses commandes uniquement
            return Order.objects.filter(user=self.request.user)
    
    def get_permissions(self):
        """Définit les permissions selon l'action."""
        if self.action in ['list', 'retrieve', 'create_from_cart', 'my_orders', 'cancel']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['pending', 'shipped', 'delivered', 'statistics', 'mark_shipped', 'mark_delivered', 'mark_processing']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Associe la commande à l'utilisateur connecté."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_from_cart(self, request):
        """Crée une commande à partir du panier actuel."""
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response(
                {'error': 'Aucun panier trouvé'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérifier que le panier n'est pas vide
        if not cart.items.exists():
            return Response(
                {'error': 'Le panier est vide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valider le panier
        is_valid, invalid_items = cart.validate_cart()
        if not is_valid:
            errors = []
            for invalid in invalid_items:
                product_name = invalid['item'].product.name
                error_msg = invalid['error']
                errors.append(f"{product_name}: {error_msg}")
            return Response(
                {'error': 'Panier invalide', 'details': errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Créer la commande avec transaction atomique
        try:
            with transaction.atomic():
                # Vérifier et verrouiller le stock
                for item in cart.items.all():
                    product = Product.objects.select_for_update().get(id=item.product.id)
                    can_purchase, message = product.can_purchase_quantity(item.quantity)
                    if not can_purchase:
                        return Response(
                            {'error': f'Stock insuffisant pour {product.name}: {message}'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                # Créer la commande
                order = Order.objects.create(
                    user=request.user,
                    cart=cart,
                    total_price=cart.total_price,
                    status='pending',
                    shipment_type=request.data.get('shipment_type', 'standard'),
                    delivery_address=request.data.get('delivery_address', ''),
                    billing_address=request.data.get('billing_address', '')
                )
                
                # Décrémenter le stock
                for item in cart.items.all():
                    product = Product.objects.select_for_update().get(id=item.product.id)
                    product.stock -= item.quantity
                    product.save()
                
                # Créer un nouveau panier vide pour l'utilisateur
                Cart.objects.create(user=request.user)
                
                serializer = self.get_serializer(order)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la création de la commande: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Récupère toutes les commandes de l'utilisateur connecté."""
        orders = self.get_queryset()
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def cancel(self, request, pk=None):
        """Annule une commande (si elle n'est pas encore expédiée)."""
        order = self.get_object()
        
        # Vérifier que l'utilisateur est propriétaire
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Utiliser votre méthode existante
        if order.cancel_order():
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        else:
            return Response(
                {'error': f'Impossible d\'annuler une commande {order.get_status_display()}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Actions réservées aux admins
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Commandes en attente (admin)."""
        orders = Order.objects.filter(status='pending')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def shipped(self, request):
        """Commandes expédiées (admin)."""
        orders = Order.objects.filter(status='shipped')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def delivered(self, request):
        """Commandes livrées (admin)."""
        orders = Order.objects.filter(status='delivered')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_processing(self, request, pk=None):
        """Marque une commande comme en cours de traitement (admin)."""
        order = self.get_object()
        
        if order.status != 'pending':
            return Response(
                {'error': 'Seules les commandes en attente peuvent être mises en traitement'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.confirm_order()  # Utilise votre méthode existante
        serializer = self.get_serializer(order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_shipped(self, request, pk=None):
        """Marque une commande comme expédiée (admin)."""
        order = self.get_object()
        
        if order.status not in ['pending', 'processing']:
            return Response(
                {'error': 'Seules les commandes en attente ou en traitement peuvent être expédiées'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'shipped'
        tracking_number = request.data.get('tracking_number', '')
        if tracking_number:
            order.set_tracking_number(tracking_number)
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_delivered(self, request, pk=None):
        """Marque une commande comme livrée (admin)."""
        order = self.get_object()
        
        if order.status != 'shipped':
            return Response(
                {'error': 'Seules les commandes expédiées peuvent être marquées comme livrées'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'delivered'
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check_tracking(self, request, pk=None):
        """Vérifie le statut de livraison via l'API transporteur (admin)."""
        order = self.get_object()
        
        if not order.tracking_number or order.tracking_number == "Non défini":
            return Response(
                {'error': 'Aucun numéro de suivi disponible'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser votre méthode existante
        delivery_status = order.check_delivery_status()
        
        if delivery_status:
            serializer = self.get_serializer(order)
            return Response({
                'order': serializer.data,
                'carrier_status': delivery_status,
                'message': 'Statut mis à jour automatiquement'
            })
        else:
            return Response(
                {'error': 'Impossible de récupérer le statut de livraison'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des commandes (admin)."""
        from django.db.models import Count, Sum
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        
        # Calculs de base
        all_orders = Order.objects.all()
        completed_orders = all_orders.filter(status__in=['delivered'])
        recent_orders = all_orders.filter(created_at__gte=last_30_days)
        
        stats = {
            'total_orders': all_orders.count(),
            'pending_orders': all_orders.filter(status='pending').count(),
            'processing_orders': all_orders.filter(status='processing').count(),
            'shipped_orders': all_orders.filter(status='shipped').count(),
            'delivered_orders': completed_orders.count(),
            'cancelled_orders': all_orders.filter(status='cancelled').count(),
            'total_revenue': completed_orders.aggregate(
                Sum('total_price')
            )['total_price__sum'] or 0,
            'orders_last_30_days': recent_orders.count(),
            'revenue_last_30_days': recent_orders.filter(
                status='delivered'
            ).aggregate(Sum('total_price'))['total_price__sum'] or 0,
        }
        
        # Statistiques par type d'expédition
        shipment_stats = {}
        for shipment_type, _ in Order.SHIPMENT_TYPES:
            shipment_stats[shipment_type] = all_orders.filter(
                shipment_type=shipment_type
            ).count()
        
        stats['shipment_types'] = shipment_stats
        
        return Response(stats)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Résumé détaillé d'une commande."""
        order = self.get_object()
        
        # Vérifier que l'utilisateur peut voir cette commande
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission refusée'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Construire le résumé avec les items du panier
        items_summary = []
        for item in order.cart.items.all():
            items_summary.append({
                'product_name': item.product.name,
                'quantity': item.quantity,
                'unit_price': item.product.promotion_price if item.product.is_on_promotion() else item.product.price,
                'total_price': item.total_price,
                'was_on_promotion': item.product.is_on_promotion()
            })
        
        summary = {
            'order_id': order.id,
            'user': order.user.name,
            'total_price': order.total_price,
            'status': order.get_status_display(),
            'shipment_type': order.get_shipment_type_display(),
            'delivery_address': order.get_delivery_address(),
            'billing_address': order.get_billing_address(),
            'tracking_number': order.tracking_number,
            'created_at': order.created_at,
            'items': items_summary,
            'total_items': order.cart.total_quantity
        }
        
        return Response(summary)
