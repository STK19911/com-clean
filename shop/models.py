from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone  # ⭐ Import pour les dates de coupon

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    stock = models.PositiveIntegerField()
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['available']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.id, self.slug])
    
    def is_in_stock(self):
        return self.stock > 0 and self.available
    
    def average_rating(self):
        """Calcule la note moyenne du produit"""
        reviews = self.reviews.filter(approved=True)
        if reviews.count() > 0:
            return round(sum(review.rating for review in reviews) / reviews.count(), 1)
        return 0
    
    def review_count(self):
        """Retourne le nombre d'avis approuvés"""
        return self.reviews.filter(approved=True).count()
    
    def has_user_ordered(self, user):
        """Vérifie si l'utilisateur a déjà commandé ce produit"""
        if not user.is_authenticated:
            return False
        # Assurez-vous que OrderItem existe (il est défini plus tard)
        # Nécessite un import local si OrderItem n'est pas encore défini
        from .models import OrderItem 
        return OrderItem.objects.filter(
            order__user=user,
            product=self
        ).exists()

# --- NOUVEAU MODÈLE POUR LES COUPONS ---
class Coupon(models.Model):
    """Modèle pour les codes promo"""
    
    CODE_TYPES = [
        ('percentage', 'Pourcentage'),
        ('fixed', 'Montant fixe'),
        ('free_shipping', 'Livraison gratuite'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Code promo en majuscules")
    description = models.TextField(blank=True, help_text="Description du code promo")
    discount_type = models.CharField(max_length=20, choices=CODE_TYPES, default='percentage')
    discount_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Pourcentage (ex: 10) ou montant fixe (ex: 15.00)"
    )
    minimum_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Montant minimum de commande pour utiliser le code"
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    max_usage = models.PositiveIntegerField(
        default=1,
        help_text="Nombre maximum d'utilisations (0 = illimité)"
    )
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    single_use_per_user = models.BooleanField(
        default=False,
        help_text="Une seule utilisation par utilisateur"
    )
    # Assurez-vous que les modèles Category et Product sont définis (ils le sont)
    categories = models.ManyToManyField(
        'Category', 
        blank=True,
        help_text="Catégories applicables (vide = toutes)"
    )
    products = models.ManyToManyField(
        'Product',
        blank=True,
        help_text="Produits applicables (vide = tous)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()} {self.discount_value}"
    
    def is_valid(self, user=None, cart=None):
        """Vérifie si le code promo est valide"""
        now = timezone.now()
        
        # Vérifications de base
        if not self.active:
            return False, "Ce code promo n'est plus actif."
        
        if now < self.valid_from:
            return False, "Ce code promo n'est pas encore valide."
        
        if now > self.valid_to:
            return False, "Ce code promo a expiré."
        
        if self.max_usage > 0 and self.used_count >= self.max_usage:
            return False, "Ce code promo a atteint sa limite d'utilisation."
        
        # Vérification utilisateur spécifique
        if user and user.is_authenticated and self.single_use_per_user:
            # Importez Order ici pour éviter les problèmes de dépendance circulaire
            from .models import Order 
            if Order.objects.filter(user=user, coupon=self).exists():
                return False, "Vous avez déjà utilisé ce code promo."
        
        # Vérification panier
        if cart:
            total_price = cart.get_total_price()
            
            if total_price < self.minimum_amount:
                return False, f"Montant minimum requis : {self.minimum_amount} €"
            
            # Vérifier les catégories/produits applicables
            if not self._is_applicable_to_cart(cart):
                return False, "Ce code promo ne s'applique pas aux articles de votre panier."
        
        return True, "Code promo valide"
    
    def _is_applicable_to_cart(self, cart):
        """Vérifie si le code s'applique au contenu du panier"""
        if not self.categories.exists() and not self.products.exists():
            return True  # Applicable à tous les produits
        
        # Utilisez une requête efficace si possible, mais le code actuel est fonctionnel
        cart_products = [item.product for item in cart.items.all()]
        
        # Vérifier les produits spécifiques
        if self.products.exists():
            if any(product in self.products.all() for product in cart_products):
                return True
        
        # Vérifier les catégories
        if self.categories.exists():
            cart_categories = {item.product.category for item in cart.items.all()}
            if any(category in self.categories.all() for category in cart_categories):
                return True
        
        return False
    
    def calculate_discount(self, amount):
        """Calcule le montant de la réduction"""
        # ✅ S'assurer que amount est Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
    
        if self.discount_type == 'percentage':
            discount = (amount * self.discount_value) / Decimal('100')
        elif self.discount_type == 'fixed':
            discount = min(self.discount_value, amount)
        else:  # free_shipping
            discount = Decimal('0')  # Géré séparément
    
        return discount
    
    def apply_discount(self, cart):
        """Applique la réduction au panier"""
        if self.discount_type == 'free_shipping':
            return 0, "Livraison gratuite appliquée"
        
        applicable_amount = self._get_applicable_amount(cart)
        discount = self.calculate_discount(applicable_amount)
        
        return discount, f"Réduction de {discount} € appliquée"
    
    def _get_applicable_amount(self, cart):
        """Retourne le montant applicable pour la réduction"""
        if not self.categories.exists() and not self.products.exists():
            return cart.get_total_price()
        
        applicable_amount = 0
        for item in cart.items.all():
            if (self.products.filter(id=item.product.id).exists() or 
                self.categories.filter(id=item.product.category.id).exists()):
                applicable_amount += item.get_total_price()
        
        return applicable_amount
    
    def mark_as_used(self):
        """Marque le code comme utilisé"""
        self.used_count += 1
        self.save()

# --- Modèles existants suivants (Cart, CartItem, Order, OrderItem, UserProfile, etc.) ---

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        if self.user:
            return f"Panier de {self.user.username}"
        return f"Panier session {self.session_key}"
    
    def get_total_price(self):
        try:
            return sum(item.get_total_price() for item in self.items.all())
        except:
            return 0
    
    def get_total_quantity(self):
        try:
            return sum(item.quantity for item in self.items.all())
        except:
            return 0
    
    def is_empty(self):
        return self.items.count() == 0

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    def get_total_price(self):
        return self.quantity * self.product.price
    
    def is_available(self):
        return self.product.is_in_stock() and self.quantity <= self.product.stock

# --- MODÈLE Order MIS À JOUR ---
class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_PROCESSING, 'En traitement'),
        (STATUS_SHIPPED, 'Expédiée'),
        (STATUS_DELIVERED, 'Livrée'),
        (STATUS_CANCELLED, 'Annulée'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='orders')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    # ⭐ NOUVEAUX CHAMPS CODES PROMO & LIVRAISON
    coupon = models.ForeignKey(
        Coupon, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders'
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    shipping_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['created']),
            models.Index(fields=['status']),
            models.Index(fields=['paid']),
        ]
    
    def __str__(self):
        return f"Commande #{self.id} - {self.first_name} {self.last_name}"
    
    def get_total_before_discount(self):
        """Retourne le total avant réduction"""
        try:
            return sum(item.get_cost() for item in self.items.all())
        except:
            return 0
    
    def get_total_cost(self):
        """Retourne le coût total après réduction et avec frais de port"""
        try:
            total = sum(item.get_cost() for item in self.items.all())
            total -= self.discount_amount
            total += self.shipping_cost
            return max(total, 0)  # Éviter les totaux négatifs
        except:
            return 0
    
    def get_total_before_discount(self):
        """Retourne le total des produits avant réduction et frais de port"""
        try:
            return sum(item.get_cost() for item in self.items.all())
        except:
            return 0
    
    def get_status_display_class(self):
        status_classes = {
            self.STATUS_PENDING: 'warning',
            self.STATUS_PROCESSING: 'info',
            self.STATUS_SHIPPED: 'primary',
            self.STATUS_DELIVERED: 'success',
            self.STATUS_CANCELLED: 'danger',
        }
        return status_classes.get(self.status, 'secondary')
    
    def can_be_cancelled(self):
        return self.status in [self.STATUS_PENDING, self.STATUS_PROCESSING]

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Commande #{self.order.id})"
    
    def get_cost(self):
        return self.price * self.quantity

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birth_date = models.DateField()
    phone_number = models.CharField(max_length=15)
    email_confirmed = models.BooleanField(default=False)
    confirmation_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Profil de {self.user.get_full_name() or self.user.email}"
    
    def get_full_name(self):
        return self.user.get_full_name()
    
    def get_age(self):
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
    
    def generate_new_confirmation_token(self):
        """Génère un nouveau token de confirmation"""
        import uuid
        self.confirmation_token = uuid.uuid4()
        self.save()
        return self.confirmation_token

class Favorite(models.Model):
    """Modèle pour les produits favoris des utilisateurs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class ProductReview(models.Model):
    """Modèle pour les avis et évaluations des produits"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Note de 1 à 5 étoiles"
    )
    title = models.CharField(max_length=100, help_text="Titre de l'avis")
    comment = models.TextField(help_text="Commentaire détaillé")
    approved = models.BooleanField(default=False, help_text="L'avis est-il approuvé ?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # NOUVEAUX CHAMPS POUR LA MODÉRATION
    reported = models.BooleanField(default=False, help_text="Avis signalé")
    report_reason = models.TextField(blank=True, help_text="Raison du signalement")
    moderator_notes = models.TextField(blank=True, help_text="Notes du modérateur")
    
    class Meta:
        unique_together = ['user', 'product']
        ordering = ['-created_at']
        verbose_name = "Avis produit"
        verbose_name_plural = "Avis produits"
    
    def __str__(self):
        return f"Avis de {self.user.username} sur {self.product.name}"
    
    def get_rating_stars(self):
        """Retourne la représentation en étoiles de la note"""
        return '★' * self.rating + '☆' * (5 - self.rating)
    
    # MÉTHODES DE MODÉRATION
    def mark_as_reported(self, reason=""):
        """Marquer l'avis comme signalé"""
        self.reported = True
        self.report_reason = reason
        self.save()
    
    def approve(self):
        """Approuver l'avis"""
        self.approved = True
        self.reported = False
        self.save()
    
    def reject(self, notes=""):
        """Rejeter l'avis"""
        self.approved = False
        self.moderator_notes = notes
        self.save()

    def mark_as_reported(self, reason=""):
        """Marquer l'avis comme signalé"""
        self.reported = True
        self.report_reason = reason
        self.save()