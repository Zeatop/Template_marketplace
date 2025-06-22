import django_filters
from django.db.models import Q, F
from .models import Product

class ProductFilter(django_filters.FilterSet):
    """Filtres pour les produits."""
    
    # ✅ Filtres de base
    category = django_filters.CharFilter(lookup_expr='iexact')
    editor = django_filters.CharFilter(lookup_expr='icontains')
    preorder = django_filters.BooleanFilter()
    
    # ✅ Filtre promotion (calculé)
    on_promotion = django_filters.BooleanFilter(method='filter_on_promotion')
    
    # ✅ Filtre disponibilité
    available = django_filters.BooleanFilter(method='filter_available')
    
    # ✅ Filtres prix
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    
    # ✅ Filtres date
    release_date_after = django_filters.DateFilter(field_name='release_date', lookup_expr='gte')
    release_date_before = django_filters.DateFilter(field_name='release_date', lookup_expr='lte')
    
    # ✅ Filtre stock
    min_stock = django_filters.NumberFilter(field_name='stock', lookup_expr='gte')
    
    class Meta:
        model = Product
        fields = ['category', 'editor', 'preorder']
    
    def filter_on_promotion(self, queryset, name, value):
        """Filtre les produits en promotion."""
        if value:
            return queryset.filter(
                promotion_price__isnull=False,
                promotion_price__lt=F('price')
            )
        else:
            return queryset.filter(
                Q(promotion_price__isnull=True) | 
                Q(promotion_price__gte=F('price'))
            )
    
    def filter_available(self, queryset, name, value):
        """Filtre les produits disponibles."""
        if value:
            return queryset.filter(stock__gt=0)
        else:
            return queryset.filter(stock=0)

'''
# ✅ Filtres de base
GET /api/products/?category=Electronics
GET /api/products/?preorder=true
GET /api/products/?on_promotion=true
GET /api/products/?available=true

# ✅ Filtres prix
GET /api/products/?min_price=100&max_price=500

# ✅ Filtres combinés
GET /api/products/?category=Gaming&on_promotion=true&available=true

# ✅ Recherche textuelle
GET /api/products/?search=iPhone

# ✅ Tri
GET /api/products/?ordering=price
GET /api/products/?ordering=-created_at

# ✅ Actions custom
GET /api/products/promotions/
GET /api/products/categories/
GET /api/products/low_stock/
'''