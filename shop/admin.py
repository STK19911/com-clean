from django.contrib import admin
from django.contrib.auth.models import User
from .models import Category, Coupon, Product, Cart, CartItem, Order, OrderItem, UserProfile, Favorite, ProductReview, Vendor  # AJOUT Vendor

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    list_filter = ['name']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'available', 'average_rating', 'review_count', 'created']
    list_filter = ['available', 'category', 'created', 'updated']
    list_editable = ['price', 'stock', 'available']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    date_hierarchy = 'created'
    ordering = ['-created']
    
    def average_rating(self, obj):
        return obj.average_rating()
    average_rating.short_description = 'Note moyenne'
    
    def review_count(self, obj):
        return obj.review_count()
    review_count.short_description = "Nb d'avis"

class CartItemInline(admin.TabularInline):
    model = CartItem
    raw_id_fields = ['product']
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'get_total_price', 'get_total_quantity', 'created']
    list_filter = ['created', 'updated']
    search_fields = ['user__username', 'user__email']
    inlines = [CartItemInline]
    date_hierarchy = 'created'
    
    def get_total_price(self, obj):
        return f"{obj.get_total_price()} €"
    get_total_price.short_description = 'Total'
    
    def get_total_quantity(self, obj):
        return obj.get_total_quantity()
    get_total_quantity.short_description = 'Quantité totale'

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'first_name', 'last_name', 'email', 'get_total_cost', 'paid', 'status', 'created']
    list_filter = ['paid', 'status', 'created', 'city']
    list_editable = ['paid', 'status']
    search_fields = ['first_name', 'last_name', 'email', 'address', 'city']
    inlines = [OrderItemInline]
    date_hierarchy = 'created'
    ordering = ['-created']
    
    def get_total_cost(self, obj):
        return f"{obj.get_total_cost()} €"
    get_total_cost.short_description = 'Total'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_full_name', 'email_confirmed', 'birth_date', 'phone_number', 'created_at']
    list_filter = ['email_confirmed', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at', 'confirmation_token']
    date_hierarchy = 'created_at'
    
    # ▼▼▼ ACTIONS SUPPRIMÉES ▼▼▼
    # actions = ['confirm_emails', 'resend_confirmation_email']
    # ▲▲▲ FIN SUPPRESSION ▲▲▲

    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Nom complet'

    # ▼▼▼ FONCTIONS D'ACTION SUPPRIMÉES ▼▼▼
    # def confirm_emails(self, request, queryset):
    #     ...
    # def resend_confirmation_email(self, request, queryset):
    #     ...
    # ▲▲▲ FIN SUPPRESSION ▲▲▲

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name']
    date_hierarchy = 'created_at'

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'title', 'approved', 'reported', 'needs_moderation', 'created_at']
    list_filter = ['approved', 'reported', 'rating', 'created_at']
    search_fields = ['user__username', 'product__name', 'title', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    actions = ['approve_reviews', 'reject_reviews', 'mark_as_reported', 'bulk_approve_trusted_users']
    
    def approve_reviews(self, request, queryset):
        """Action pour approuver les avis"""
        updated = queryset.update(approved=True, reported=False)
        self.message_user(request, f'{updated} avis approuvé(s).')
    approve_reviews.short_description = "Approuver les avis sélectionnés"
    
    def reject_reviews(self, request, queryset):
        """Action pour rejeter les avis"""
        updated = queryset.update(approved=False)
        self.message_user(request, f'{updated} avis rejeté(s).')
    reject_reviews.short_description = "Rejeter les avis sélectionnés"
    
    def mark_as_reported(self, request, queryset):
        """Action pour marquer comme signalé"""
        updated = queryset.update(reported=True)
        self.message_user(request, f'{updated} avis marqué(s) comme signalé(s).')
    mark_as_reported.short_description = "Marquer comme signalé"
    
    def bulk_approve_trusted_users(self, request, queryset):
        """Approuver automatiquement les utilisateurs de confiance"""
        from django.db.models import Count
        
        trusted_users = User.objects.annotate(
            review_count=Count('reviews')
        ).filter(review_count__gte=3)
        
        updated = queryset.filter(user__in=trusted_users).update(approved=True)
        self.message_user(request, f'{updated} avis d\'utilisateurs de confiance approuvés.')
    bulk_approve_trusted_users.short_description = "Approuver utilisateurs de confiance"
    
    # ✅ CHAMPS PERSONNALISÉS DANS L'ADMIN
    def needs_moderation(self, obj):
        return not obj.approved or obj.reported
    needs_moderation.boolean = True
    needs_moderation.short_description = "Modération nécessaire"

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'description', 'discount_type', 'discount_value', 
        'minimum_amount', 'valid_from', 'valid_to', 'used_count', 
        'max_usage', 'active', 'created_at'
    ]
    list_filter = [
        'discount_type', 'active', 'valid_from', 'valid_to', 
        'single_use_per_user', 'created_at'
    ]
    list_editable = ['active', 'max_usage']
    search_fields = ['code', 'description']
    filter_horizontal = ['categories', 'products']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations de base', {
            'fields': (
                'code', 'description', 'active',
                'discount_type', 'discount_value', 'minimum_amount'
            )
        }),
        ('Période de validité', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Limites d\'utilisation', {
            'fields': ('max_usage', 'single_use_per_user')
        }),
        ('Restrictions', {
            'fields': ('categories', 'products'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('used_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_coupons', 'deactivate_coupons', 'reset_usage_count']
    
    def activate_coupons(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} code(s) promo activé(s).')
    activate_coupons.short_description = "Activer les codes promo sélectionnés"
    
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} code(s) promo désactivé(s).')
    deactivate_coupons.short_description = "Désactiver les codes promo sélectionnés"
    
    def reset_usage_count(self, request, queryset):
        updated = queryset.update(used_count=0)
        self.message_user(request, f'{updated} compteur(s) d\'utilisation remis à zéro.')
    reset_usage_count.short_description = "Remettre à zéro le compteur d'utilisation"

# --- AJOUT : ADMIN POUR VENDOR ---
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'is_approved', 'total_sales', 'created_at']
    list_filter = ['is_approved', 'country', 'created_at']
    search_fields = ['shop_name', 'user__email', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'total_sales', 'total_orders']
    fieldsets = (
        ("Boutique", {
            'fields': ('user', 'shop_name', 'slug', 'logo', 'banner')
        }),
        ("Présentation", {
            'fields': ('description', 'short_bio')
        }),
        ("Contact", {
            'fields': ('phone', 'website', 'instagram', 'address', 'city', 'country')
        }),
        ("Finances", {
            'fields': ('commission_rate',)
        }),
        ("Modération", {
            'fields': ('is_approved', 'approved_at', 'rejected_reason'),
            'classes': ('collapse',)
        }),
        ("Stats", {
            'fields': ('total_sales', 'total_orders', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_vendors', 'reject_vendors']

    def approve_vendors(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_approved=True, approved_at=timezone.now())
        self.message_user(request, f"{updated} boutique(s) approuvée(s).")
    approve_vendors.short_description = "Approuver les boutiques"

    def reject_vendors(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} boutique(s) refusée(s).")
    reject_vendors.short_description = "Refuser les boutiques"