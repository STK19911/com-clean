from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify

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
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    
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
        reviews = self.reviews.filter(approved=True)
        if reviews.count() > 0:
            return round(sum(review.rating for review in reviews) / reviews.count(), 1)
        return 0
    
    def review_count(self):
        return self.reviews.filter(approved=True).count()
    
    def has_user_ordered(self, user):
        if not user.is_authenticated:
            return False
        from .models import OrderItem 
        return OrderItem.objects.filter(
            order__user=user,
            product=self
        ).exists()

class Coupon(models.Model):
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
    single_use_per_user = models.BooleanField(default=False, help_text="Limité à une utilisation par utilisateur")
    categories = models.ManyToManyField(Category, blank=True, help_text="Catégories spécifiques")
    products = models.ManyToManyField(Product, blank=True, help_text="Produits spécifiques")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.code
    
    def is_valid(self, user=None, cart=None):
        now = timezone.now()
        if not self.active or now < self.valid_from or now > self.valid_to:
            return False, "Ce code promo n'est pas valide actuellement."
        if self.max_usage > 0 and self.used_count >= self.max_usage:
            return False, "Ce code promo a atteint sa limite d'utilisation."
        if self.single_use_per_user and user and self.used_by.filter(id=user.id).exists():
            return False, "Vous avez déjà utilisé ce code promo."
        if cart and self.minimum_amount > 0:
            total = cart.get_total_price()
            if total < self.minimum_amount:
                return False, f"Le montant minimum est de {self.minimum_amount} €."
        if cart and (self.categories.exists() or self.products.exists()):
            cart_products = [item.product for item in cart.items.all()]
            matches = any(
                p in self.products.all() or p.category in self.categories.all()
                for p in cart_products
            )
            if not matches:
                return False, "Ce code ne s'applique pas aux produits de votre panier."
        return True, "Valide"
    
    def calculate_discount(self, total):
        if self.discount_type == 'fixed':
            return min(self.discount_value, total)
        elif self.discount_type == 'percentage':
            return (self.discount_value / 100) * total
        elif self.discount_type == 'free_shipping':
            return Decimal('0')
        return Decimal('0')
    
    def increment_usage(self, user=None):
        self.used_count += 1
        if user and self.single_use_per_user:
            self.used_by.add(user)
        self.save()

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    # ▼▼▼ CORRECTION ICI ▼▼▼
    updated = models.DateTimeField(auto_now=True) # Remplacer auto_now_True par auto_now=True
    # ▲▲▲ FIN CORRECTION ▲▲▲
    
    class Meta:
        ordering = ['-updated']
    
    def __str__(self):
        return f"Panier de {self.user if self.user else 'Anonyme'}"
    
    def get_total_price(self):
        return sum(item.get_cost() for item in self.items.all())
    
    def get_total_quantity(self):
        return sum(item.quantity for item in self.items.all())
    
    def get_discount(self, coupon):
        if not coupon:
            return Decimal('0')
        return coupon.calculate_discount(self.get_total_price())
    
    def get_final_price(self, coupon=None):
        total = self.get_total_price()
        discount = self.get_discount(coupon) if coupon else Decimal('0')
        return total - discount

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    def get_cost(self):
        return self.price * self.quantity
    
    def is_available(self):
        return self.product.available and self.product.stock >= self.quantity

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-created']
        indexes = [models.Index(fields=['-created'])]
    
    def __str__(self):
        return f"Commande {self.id}"
    
    def get_total_cost(self):
        total = sum(item.get_cost() for item in self.items.all())
        return total - self.discount
    
    def get_absolute_url(self):
        return reverse('shop:order_detail', args=[self.id])

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return str(self.id)
    
    def get_cost(self):
        return self.price * self.quantity

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    email_confirmed = models.BooleanField(default=True) # C'est bien 'True' comme on l'a défini
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
        import uuid
        self.confirmation_token = uuid.uuid4()
        self.save()
        return self.confirmation_token

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class ProductReview(models.Model):
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
        return '★' * self.rating + '☆' * (5 - self.rating)
    
    def mark_as_reported(self, reason=""):
        self.reported = True
        self.report_reason = reason
        self.save()
    
    def approve(self):
        self.approved = True
        self.reported = False
        self.save()
    
    def reject(self, notes=""):
        self.approved = False
        self.moderator_notes = notes
        self.save()

class Vendor(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='vendor_profile'
    )
    shop_name = models.CharField(
        max_length=120,
        unique=True,
        help_text="Nom public de votre boutique (ex: « Maison Éternelle »)"
    )
    slug = models.SlugField(max_length=130, unique=True, blank=True)
    logo = models.ImageField(
        upload_to='vendors/logos/',
        blank=True,
        help_text="Logo carré 400×400px recommandé"
    )
    banner = models.ImageField(
        upload_to='vendors/banners/',
        blank=True,
        help_text="Bannière 1920×600px"
    )
    description = models.TextField(
        max_length=1000,
        blank=True,
        help_text="Présentez votre histoire, votre savoir-faire…"
    )
    short_bio = models.CharField(
        max_length=160,
        blank=True,
        help_text="Phrase d’accroche (meta description)"
    )
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="France")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        validators=[MinValueValidator(0)],
        help_text="Pourcentage prélevé par LuxuryZone (ex: 15%)"
    )
    is_approved = models.BooleanField(
        default=False,
        help_text="Cochez pour activer la boutique"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Boutique Vendeur"
        verbose_name_plural = "Boutiques Vendeurs"
        ordering = ['-created_at']

    def __str__(self):
        return self.shop_name

    def get_absolute_url(self):
        return reverse('shop:vendor_shop', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.shop_name)
            unique_slug = self.slug
            num = 1
            while Vendor.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{self.slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def pending_orders(self):
        return self.orders.filter(status='processing').count()

    def monthly_revenue(self):
        from django.utils import timezone
        from datetime import timedelta
        last_month = timezone.now() - timedelta(days=30)
        return self.orders.filter(
            created__gte=last_month,
            paid=True
        ).aggregate(total=models.Sum('get_total_cost'))['total'] or Decimal('0')