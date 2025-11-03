from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Order
from django.core.exceptions import ValidationError
import re
from .models import Vendor
from .models import Order, ProductReview, Product, Category, Vendor
class CartAddProductForm(forms.Form):
    """
    Formulaire pour ajouter des produits au panier
    """
    quantity = forms.IntegerField(
        min_value=1,
        max_value=20,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'width: 80px;'
        })
    )
    update = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput
    )

class OrderCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une commande
    """
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'address', 'postal_code', 'city']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code postal'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville'
            }),
        }
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Adresse email',
            'address': 'Adresse',
            'postal_code': 'Code postal', 
            'city': 'Ville',
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre@email.com'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre prénom'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom'
        })
    )
    birth_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'JJ/MM/AAAA'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+33 6 12 34 56 78'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'birth_date', 'phone_number', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        # Format international simple
        if not re.match(r'^\+?[\d\s-]{10,15}$', phone):
            raise ValidationError("Numéro de téléphone invalide. Ex: +33 6 12 34 56 78")
        return phone

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')
        from datetime import date
        age = (date.today() - birth_date).days / 365.25
        if age < 18:
            raise ValidationError("Vous devez avoir au moins 18 ans.")
        return birth_date

class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f"{i} étoiles") for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre de votre avis (ex: Excellent produit)'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Détaillez votre expérience...'
            }),
        }
        labels = {
            'rating': 'Note',
            'title': 'Titre',
            'comment': 'Commentaire',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_title(self):
        """Filtre pour le titre"""
        title = self.cleaned_data.get('title')
        
        # Liste de mots inappropriés (élargie)
        inappropriate_words = [
            # Mots existants (Nettoyage de base)
            'spam', 'arnaque', 'escroc', 
            
            # Insultes/Vulgarité
            'merde', 'con', 'connard', 'pute', 'salope', 'putain', 
            'enculé', 'bâtard', 'abruti', 'idiot', 'débile', 'chienne', 
            'foutre', 'bordel',
            
            # Contenu sexuel/Nudité
            'nue', 'nude', 'sexe', 'viol', 'porn', 'porno', 'masturb', 'sodom', 'gode', 'bite', 'chatte', 'queue',
            
            # Violence/Haine/Menaces
            'violent', 'meutre', 'tuer', 'massacre', 'raciste', 'nazi', 'terror', 'haineux', 'frapper', 'suicide',
            
            # Substances illicites
            'drogue', 'coke', 'héroïne', 'crack', 'toxico',
            
            # Termes Financiers Trompeurs
            'gratuit', 'remboursement immédiat', 'sans risque', 'facile', 'rapide', # À utiliser avec prudence selon le contexte
        ]
        
        # Vérifier la longueur
        if len(title) < 5:
            raise ValidationError("Le titre doit contenir au moins 5 caractères.")
        
        if len(title) > 100:
            raise ValidationError("Le titre ne peut pas dépasser 100 caractères.")
        
        # Vérifier les mots inappropriés
        for word in inappropriate_words:
            if word in title.lower():
                raise ValidationError("Le titre contient des mots inappropriés.")
        
        return title
    
    def clean_comment(self):
        """Filtre pour le commentaire"""
        comment = self.cleaned_data.get('comment')
        
        # Liste de mots inappropriés
        inappropriate_words = [
    # Mots existants (Nettoyage de base)
    'spam', 'arnaque', 'escroc', 
    
    # Insultes/Vulgarité
    'merde', 'con', 'connard', 'pute', 'salope', 'putain', 
    'enculé', 'bâtard', 'abruti', 'idiot', 'débile', 'chienne', 
    'foutre', 'bordel',
    
    # Contenu sexuel/Nudité
    'nue', 'nude', 'sexe', 'viol', 'porn', 'porno', 'masturb', 'sodom', 'gode', 'bite', 'chatte', 'queue',
    
    # Violence/Haine/Menaces
    'violent', 'meutre', 'tuer', 'massacre', 'raciste', 'nazi', 'terror', 'haineux', 'frapper', 'suicide',
    
    # Substances illicites
    'drogue', 'coke', 'héroïne', 'crack', 'toxico',
    
    # Termes Financiers Trompeurs
    'gratuit', 'remboursement immédiat', 'sans risque', 'facile', 'rapide', # À utiliser avec prudence selon le contexte
]
        
        # Vérifier la longueur
        if len(comment) < 10:
            raise ValidationError("Le commentaire doit contenir au moins 10 caractères.")
        
        if len(comment) > 1000:
            raise ValidationError("Le commentaire ne peut pas dépasser 1000 caractères.")
        
        # Vérifier les mots inappropriés
        for word in inappropriate_words:
            if word in comment.lower():
                raise ValidationError("Le commentaire contient des mots inappropriés.")
        
        # Vérifier le ratio majuscules/minuscules (éviter les cris)
        if len(comment) > 20:
            uppercase_count = sum(1 for c in comment if c.isupper())
            if uppercase_count / len(comment) > 0.5:
                raise ValidationError("Veuillez éviter d'écrire en majuscules.")
        
        return comment
    
    def clean_rating(self):
        """Filtre pour la note"""
        rating = self.cleaned_data.get('rating')
        
        # ✅ CORRECTION : Vérifier si l'utilisateur est disponible
        if self.user and self.user.is_authenticated:
            # Vérifier les notes extrêmes (1 ou 5) pour les nouveaux utilisateurs
            user_reviews = ProductReview.objects.filter(user=self.user)
            if user_reviews.count() < 3 and rating in [1, 5]:
                # Pour les nouveaux utilisateurs, demander un commentaire plus détaillé
                comment = self.cleaned_data.get('comment', '')
                if len(comment) < 50:
                    raise ValidationError(
                        "Pour les notes extrêmes (1 ou 5 étoiles), veuillez fournir "
                        "un commentaire détaillé d'au moins 50 caractères expliquant votre évaluation."
                    )
        
        return rating

# ✅ NOUVEAU FORMULAIRE POUR LES COUPONS
class CouponApplyForm(forms.Form):
    """Formulaire pour appliquer un code promo"""
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrez votre code promo',
            'style': 'text-transform: uppercase;'
        }),
        label="Code promo"
    )
    
    def clean_code(self):
        """Normalise le code promo en majuscules et sans espaces inutiles"""
        code = self.cleaned_data.get('code').upper().strip()
        return code

# --- AJOUT : FORMULAIRE POUR AJOUTER/MODIFIER PRODUITS PAR VENDEURS ---
class VendorProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'slug', 'description', 'price', 'image', 'stock', 'available']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du produit'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-généré si vide'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# --- OPTIONNEL : FORMULAIRE D'INSCRIPTION VENDEUR ---
class VendorRegistrationForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['shop_name', 'description', 'logo', 'banner', 'phone', 'website', 'instagram', 'address', 'city', 'country']
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de votre boutique'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'banner': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'instagram': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}, choices=[('France', 'France')]),  # Ajoute plus si besoin
        }