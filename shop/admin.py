from django.contrib import admin
from django.contrib.auth.models import User
from .models import Category, Coupon, Product, Cart, CartItem, Order, OrderItem, UserProfile, Favorite, ProductReview

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
    
    actions = ['confirm_emails', 'resend_confirmation_email']

    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Nom complet'

    def confirm_emails(self, request, queryset):
        """Action pour confirmer manuellement les emails"""
        updated = queryset.update(email_confirmed=True)
        self.message_user(request, f'{updated} compte(s) confirmé(s) avec succès.')
    confirm_emails.short_description = "Confirmer les emails sélectionnés"

    def resend_confirmation_email(self, request, queryset):
        """Action pour renvoyer l'email de confirmation"""
        from .email_service import send_confirmation_email
        count = 0
        for profile in queryset:
            if not profile.email_confirmed:
                profile.generate_new_confirmation_token()
                send_confirmation_email(profile.user)
                count += 1
        self.message_user(request, f'{count} email(s) de confirmation renvoyé(s).')
    resend_confirmation_email.short_description = "Renvoyer l'email de confirmation"

# ✅ NOUVEAUX ADMIN POUR FAVORIS ET AVIS

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name']
    date_hierarchy = 'created_at'

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'title', 'approved', 'reported', 'created_at']
    list_filter = ['approved', 'reported', 'rating', 'created_at']
    list_editable = ['approved']
    search_fields = ['user__username', 'product__name', 'title', 'comment']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['approve_reviews', 'disapprove_reviews', 'mark_as_reported', 'bulk_approve_trusted_users']
    
    # ✅ FILTRES PERSONNALISÉS POUR L'ADMIN
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Par défaut, montrer d'abord les avis nécessitant une modération
        if request.path == '/admin/shop/productreview/':
            return qs.order_by('approved', 'reported', '-created_at')
        return qs
    
    def approve_reviews(self, request, queryset):
        """Action pour approuver les avis sélectionnés"""
        updated = queryset.update(approved=True, reported=False)
        self.message_user(request, f'{updated} avis approuvé(s).')
    approve_reviews.short_description = "Approuver les avis sélectionnés"
    
    def disapprove_reviews(self, request, queryset):
        """Action pour désapprouver les avis sélectionnés"""
        updated = queryset.update(approved=False)
        self.message_user(request, f'{updated} avis désapprouvé(s).')
    disapprove_reviews.short_description = "Désapprouver les avis sélectionnés"
    
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
    
    list_display = ['user', 'product', 'rating', 'title', 'approved', 'reported', 'needs_moderation', 'created_at']

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