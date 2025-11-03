from datetime import timezone
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .forms import CartAddProductForm, CouponApplyForm, OrderCreateForm, CustomUserCreationForm, ProductReviewForm
from .models import Category, Coupon, Product, Cart, CartItem, Order, OrderItem, UserProfile, Favorite, ProductReview
from .email_service import send_confirmation_email, send_welcome_email
import uuid
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator



# Vues Produits
def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    return render(request, 'shop/product/list.html', {
        'category': category,
        'categories': categories,
        'products': products
    })

def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    cart_product_form = CartAddProductForm()
    
    # ✅ CONTEXTE POUR LES FAVORIS ET AVIS
    is_favorite = False
    user_review = None
    can_review = False
    
    if request.user.is_authenticated:
        # Vérifier si le produit est en favoris
        is_favorite = Favorite.objects.filter(user=request.user, product=product).exists()
        # Récupérer l'avis de l'utilisateur s'il existe
        user_review = ProductReview.objects.filter(user=request.user, product=product).first()
        # Vérifier si l'utilisateur peut laisser un avis (a commandé le produit)
        can_review = product.has_user_ordered(request.user)
    
    # Récupérer les avis approuvés
    approved_reviews = product.reviews.filter(approved=True).order_by('-created_at')
    
    return render(request, 'shop/product/detail.html', {
        'product': product,
        'cart_product_form': cart_product_form,
        'is_favorite': is_favorite,
        'user_review': user_review,
        'can_review': can_review,
        'approved_reviews': approved_reviews,
        'review_form': ProductReviewForm()
    })

# Vues Panier
def _get_cart(request):
    """Récupère ou crée le panier pour l'utilisateur ou la session"""
    try:
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=request.user)
        else:
            cart_id = request.session.get('cart_id')
            if cart_id:
                try:
                    cart = Cart.objects.get(id=cart_id)
                except Cart.DoesNotExist:
                    cart = Cart.objects.create()
                    request.session['cart_id'] = cart.id
            else:
                cart = Cart.objects.create()
                request.session['cart_id'] = cart.id
        return cart
    except Exception as e:
        # Fallback en cas d'erreur
        cart = Cart.objects.create()
        if request.user.is_authenticated:
            cart.user = request.user
            cart.save()
        return cart

def cart_detail(request):
    cart = _get_cart_with_discount(request)
    coupon_form = CouponApplyForm()  # ✅ AJOUTEZ CE FORMULAIRE
    
    # VÉRIFIER LA DISPONIBILITÉ DES ARTICLES
    for item in cart.items.all():
        if not item.is_available():
            messages.warning(request, 
                f"Stock insuffisant pour {item.product.name}. "
                f"Quantité disponible : {item.product.stock}"
            )
    
    return render(request, 'shop/cart/detail.html', {
        'cart': cart,
        'coupon_form': coupon_form  # ✅ AJOUTEZ LE FORMULAIRE AU CONTEXTE
    })

@csrf_protect
@require_POST
def cart_add(request, product_id):
    cart = _get_cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST)
    
    if form.is_valid():
        cd = form.cleaned_data
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': cd['quantity']}
        )
        if not created:
            if cd['update']:
                cart_item.quantity = cd['quantity']
            else:
                cart_item.quantity += cd['quantity']
            cart_item.save()
        
        messages.success(request, f"{product.name} ajouté au panier")
    
    return redirect('shop:cart_detail')

@csrf_protect
def cart_remove(request, product_id):
    cart = _get_cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.items.filter(product=product).delete()
    messages.success(request, f"{product.name} retiré du panier")
    return redirect('shop:cart_detail')

@csrf_protect
@require_POST
def cart_update(request, product_id):
    cart = _get_cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity > 0:
        cart_item = get_object_or_404(CartItem, cart=cart, product=product)
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, "Quantité mise à jour")
    else:
        cart_remove(request, product_id)
    
    return redirect('shop:cart_detail')

# Vues Commandes
@login_required
def order_create(request):
    cart = _get_cart_with_discount(request)
    
    if cart.items.count() == 0:
        messages.warning(request, "Votre panier est vide")
        return redirect('shop:product_list')
    
    # VÉRIFIER LE STOCK AVANT DE PASSER LA COMMANDE
    for cart_item in cart.items.all():
        if cart_item.quantity > cart_item.product.stock:
            messages.error(request, 
                f"Stock insuffisant pour {cart_item.product.name}. "
                f"Stock disponible : {cart_item.product.stock}"
            )
            return redirect('shop:cart_detail')
    
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            
            # ✅ GESTION DU COUPON
            coupon_id = request.session.get('coupon_id')
            if coupon_id:
                try:
                    coupon = Coupon.objects.get(id=coupon_id)
                    order.coupon = coupon
                    order.discount_amount = cart.discount_amount
                    
                    # Marquer le coupon comme utilisé
                    coupon.mark_as_used()
                except Coupon.DoesNotExist:
                    pass
            
            order.shipping_cost = cart.shipping_cost
            order.save()
            
            try:
                # Créer les OrderItems et mettre à jour le stock
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        price=cart_item.product.price,
                        quantity=cart_item.quantity
                    )
                    
                    # METTRE À JOUR LE STOCK
                    product = cart_item.product
                    product.stock -= cart_item.quantity
                    
                    if product.stock <= 0:
                        product.available = False
                    
                    product.save()
                
                # Vider le panier et les données de coupon
                cart.items.all().delete()
                clear_coupon_session(request)
                
                messages.success(request, f"Commande #{order.id} passée avec succès !")
                return redirect('shop:order_created', order_id=order.id)
                
            except Exception as e:
                order.delete()
                messages.error(request, "Une erreur est survenue lors de la commande.")
                return redirect('shop:cart_detail')
                
    else:
        # Pré-remplir avec les infos de l'utilisateur connecté
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            }
        form = OrderCreateForm(initial=initial)
    
    return render(request, 'shop/order/create.html', {
        'cart': cart,
        'form': form
    })

def order_created(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'shop/order/created.html', {'order': order})

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'shop/order/history.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order/detail.html', {'order': order})

# ✅ NOUVELLES VUES POUR LES FAVORIS

@login_required
@require_POST
def toggle_favorite(request, product_id):
    """Ajouter ou retirer un produit des favoris"""
    product = get_object_or_404(Product, id=product_id)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if not created:
        # Si le favori existe déjà, le supprimer
        favorite.delete()
        is_favorite = False
        message = "Produit retiré des favoris"
    else:
        is_favorite = True
        message = "Produit ajouté aux favoris"
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Requête AJAX
        return JsonResponse({
            'is_favorite': is_favorite,
            'message': message
        })
    
    messages.success(request, message)
    return redirect('shop:product_detail', id=product.id, slug=product.slug)

@login_required
def favorite_list(request):
    """Afficher la liste des produits favoris"""
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    return render(request, 'shop/favorites/list.html', {
        'favorites': favorites
    })

# ✅ NOUVELLES VUES POUR LES AVIS

@login_required
def add_review(request, product_id):
    """Ajouter ou modifier un avis sur un produit avec modération automatique"""
    product = get_object_or_404(Product, id=product_id)
    
    # Vérifier si l'utilisateur a commandé le produit
    if not product.has_user_ordered(request.user):
        messages.error(request, "Vous devez avoir commandé ce produit pour laisser un avis.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)
    
    # Vérifier si un avis existe déjà
    review = ProductReview.objects.filter(user=request.user, product=product).first()
    
    # ✅ FILTRES SUPPLÉMENTAIRES
    # Empêcher les avis trop rapprochés
    recent_reviews = ProductReview.objects.filter(
        user=request.user,
        created_at__gte=timezone.now() - timezone.timedelta(hours=1)
    )
    if recent_reviews.count() >= 3:
        messages.error(request, "Vous avez soumis trop d'avis récemment. Veuillez patienter avant d'en soumettre un nouveau.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)
    
    if request.method == 'POST':
        # ✅ CORRECTION : Passez l'utilisateur au formulaire
        form = ProductReviewForm(request.POST, instance=review, user=request.user)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            
            # ✅ MODÉRATION AUTOMATIQUE (passe request.user en paramètre)
            review = apply_automatic_moderation(review, request.user)
            
            review.save()
            
            if review.approved:
                messages.success(request, "Votre avis a été publié avec succès !")
            else:
                messages.success(request, 
                    "Votre avis a été enregistré. Il sera examiné par notre équipe "
                    "de modération avant publication."
                )
            
            return redirect('shop:product_detail', id=product.id, slug=product.slug)
    else:
        # ✅ CORRECTION : Passez l'utilisateur au formulaire aussi pour GET
        form = ProductReviewForm(instance=review, user=request.user)
    
    return render(request, 'shop/reviews/add.html', {
        'product': product,
        'form': form,
        'review': review
    })

def apply_automatic_moderation(review, user):
    """Applique la modération automatique aux avis"""
    
    # ✅ RÈGLES DE MODÉRATION AUTOMATIQUE
    
    # 1. Approuver automatiquement les utilisateurs de confiance
    # Utilise l'utilisateur passé en paramètre au lieu de review.user
    user_review_count = ProductReview.objects.filter(user=user).count()
    if user_review_count >= 5:
        # Utilisateur avec au moins 5 avis précédents
        review.approved = True
        return review
    
    # 2. Approuver automatiquement les notes modérées (2-4) avec bon contenu
    if review.rating in [2, 3, 4]:
        comment = review.comment.lower()
        title = review.title.lower()
        
        # Vérifier la qualité du contenu
        good_indicators = ['bon', 'bien', 'correct', 'satisfait', 'recommandé', 'qualité']
        has_good_content = any(indicator in comment for indicator in good_indicators) or len(comment) > 50
        
        if has_good_content:
            review.approved = True
            return review
    
    # 3. Modération manuelle pour les cas sensibles
    sensitive_indicators = [
        'arnaque', 'escroc', 'vol', 'arnaqu', 'inutil', 'nul', 'horrible', 'terrible','putain'
    ]
    
    comment_lower = review.comment.lower()
    title_lower = review.title.lower()
    
    for indicator in sensitive_indicators:
        if indicator in comment_lower or indicator in title_lower:
            review.approved = False
            review.moderator_notes = f"Contenu sensible détecté: {indicator}"
            return review
    
    # 4. Modération manuelle pour les notes extrêmes
    if review.rating in [1, 5]:
        if len(review.comment) < 30:
            review.approved = False
            review.moderator_notes = "Note extrême avec commentaire trop court"
            return review
    
    # Par défaut, modération manuelle
    review.approved = False
    return review

# ✅ NOUVELLE VUE POUR SIGNALER UN AVIS
@login_required
@require_POST
def report_review(request, review_id):
    """Permet aux utilisateurs de signaler un avis inapproprié"""
    review = get_object_or_404(ProductReview, id=review_id)
    
    # Empêcher de signaler son propre avis
    if review.user == request.user:
        messages.error(request, "Vous ne pouvez pas signaler votre propre avis.")
        return redirect('shop:product_detail', id=review.product.id, slug=review.product.slug)
    
    reason = request.POST.get('reason', '')
    review.mark_as_reported(reason)
    
    messages.success(request, "L'avis a été signalé à notre équipe de modération. Merci !")
    return redirect('shop:product_detail', id=review.product.id, slug=review.product.slug)

@login_required
def delete_review(request, review_id):
    """Supprimer un avis"""
    review = get_object_or_404(ProductReview, id=review_id, user=request.user)
    product = review.product
    review.delete()
    
    messages.success(request, "Votre avis a été supprimé.")
    return redirect('shop:product_detail', id=product.id, slug=product.slug)

# Vues Authentification
def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, 'Vous êtes déjà connecté.')
        return redirect('shop:product_list')
    
    if request.method == 'POST':
        # Utiliser l'email pour l'authentification
        email = request.POST.get('username')
        password = request.POST.get('password')
        
        # Trouver l'utilisateur par email
        try:
            user = User.objects.get(email=email)
            # Authentifier avec le username
            user = authenticate(username=user.username, password=password)
            
            if user is not None:
                if hasattr(user, 'profile') and user.profile.email_confirmed:
                    login(request, user)
                    
                    # TRANSFERT DU PANIER SESSION VERS UTILISATEUR
                    _transfer_session_cart_to_user(request, user)
                    
                    messages.success(request, f'Bienvenue {user.first_name} !')
                    next_page = request.GET.get('next', 'shop:product_list')
                    return redirect(next_page)
                else:
                    messages.error(request, 
                        'Votre compte n\'est pas encore confirmé. '
                        'Veuillez vérifier votre email et cliquer sur le lien de confirmation.'
                    )
            else:
                messages.error(request, 'Email ou mot de passe incorrect.')
                
        except User.DoesNotExist:
            messages.error(request, 'Aucun compte trouvé avec cet email.')
    
    return render(request, 'shop/auth/login.html')

def _transfer_session_cart_to_user(request, user):
    """Transfère le panier de session vers l'utilisateur connecté"""
    try:
        session_cart_id = request.session.get('cart_id')
        if session_cart_id:
            # Récupérer le panier de session
            session_cart = Cart.objects.get(id=session_cart_id)
            
            # Récupérer ou créer le panier utilisateur
            user_cart, created = Cart.objects.get_or_create(user=user)
            
            if not created and session_cart.items.exists():
                # Fusionner les paniers
                for session_item in session_cart.items.all():
                    user_item, item_created = CartItem.objects.get_or_create(
                        cart=user_cart,
                        product=session_item.product,
                        defaults={'quantity': session_item.quantity}
                    )
                    if not item_created:
                        user_item.quantity += session_item.quantity
                        user_item.save()
            
            # Supprimer l'ancien panier de session
            session_cart.delete()
            del request.session['cart_id']
            
    except Exception as e:
        # En cas d'erreur, on ignore simplement le transfert
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors du transfert du panier: {e}")

def logout_view(request):
    """Déconnexion de l'utilisateur"""
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'Vous avez été déconnecté avec succès.')
    else:
        messages.info(request, 'Vous n\'êtes pas connecté.')
    
    return redirect('shop:product_list')

def register_view(request):
    if request.user.is_authenticated:
        messages.info(request, 'Vous êtes déjà connecté.')
        return redirect('shop:product_list')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Envoyer l'email de confirmation
            send_confirmation_email(user)
            
            messages.success(request, 
                f'Compte créé avec succès pour {user.first_name} {user.last_name} ! '
                f'Un email de confirmation a été envoyé à {user.email}. '
                f'Veuillez vérifier votre boîte mail et cliquer sur le lien de confirmation.'
            )
            return redirect('shop:login')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'shop/auth/register.html', {'form': form})

def confirm_email_view(request, token):
    """Vue pour confirmer l'email"""
    try:
        # CORRECTION : Le token est déjà un objet UUID, pas besoin de conversion
        profile = get_object_or_404(UserProfile, confirmation_token=token)
        
        if not profile.email_confirmed:
            profile.email_confirmed = True
            profile.save()
            
            # Envoyer l'email de bienvenue
            send_welcome_email(profile.user)
            
            messages.success(request, 
                'Votre email a été confirmé avec succès ! '
                'Vous pouvez maintenant vous connecter.'
            )
        else:
            messages.info(request, 'Votre email est déjà confirmé.')
            
    except UserProfile.DoesNotExist:
        messages.error(request, 'Lien de confirmation invalide ou expiré.')
    except Exception as e:
        # Log l'erreur pour le débogage
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors de la confirmation d'email: {e}")
        messages.error(request, 'Une erreur est survenue lors de la confirmation.')
    
    return redirect('shop:login')

@login_required
def resend_confirmation_email(request):
    """Renvoyer l'email de confirmation"""
    if not hasattr(request.user, 'profile'):
        messages.error(request, 'Profil utilisateur non trouvé.')
        return redirect('shop:profile')
    
    if request.user.profile.email_confirmed:
        messages.info(request, 'Votre email est déjà confirmé.')
        return redirect('shop:profile')
    
    # Régénérer le token
    request.user.profile.confirmation_token = uuid.uuid4()
    request.user.profile.save()
    
    send_confirmation_email(request.user)
    
    messages.success(request, 
        'Un nouvel email de confirmation a été envoyé. '
        'Veuillez vérifier votre boîte mail.'
    )
    return redirect('shop:profile')

@login_required
def profile_view(request):
    """Profil de l'utilisateur"""
    # Récupérer l'historique des commandes de l'utilisateur
    orders = Order.objects.filter(user=request.user).order_by('-created')[:5]
    # Récupérer les favoris
    favorites_count = Favorite.objects.filter(user=request.user).count()
    # Récupérer les avis
    reviews_count = ProductReview.objects.filter(user=request.user).count()
    
    return render(request, 'shop/auth/profile.html', {
        'user': request.user,
        'orders': orders,
        'favorites_count': favorites_count,
        'reviews_count': reviews_count
    })

@login_required
def admin_confirm_email(request, user_id):
    """Vue pour permettre aux administrateurs de confirmer manuellement les emails"""
    if not request.user.is_superuser:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect('shop:product_list')
    
    user = get_object_or_404(User, id=user_id)
    if hasattr(user, 'profile'):
        user.profile.email_confirmed = True
        user.profile.save()
        messages.success(request, f"Le compte de {user.email} a été confirmé manuellement.")
    else:
        messages.error(request, "Profil utilisateur non trouvé.")
    
    return redirect('admin:shop_userprofile_changelist')

@login_required
@require_POST
def report_review(request, review_id):
    """Permet aux utilisateurs de signaler un avis inapproprié"""
    review = get_object_or_404(ProductReview, id=review_id)
    
    # Empêcher de signaler son propre avis
    if review.user == request.user:
        messages.error(request, "Vous ne pouvez pas signaler votre propre avis.")
        return redirect('shop:product_detail', id=review.product.id, slug=review.product.slug)
    
    reason = request.POST.get('reason', '')
    custom_reason = request.POST.get('custom_reason', '')
    
    # Combiner les raisons
    full_reason = reason
    if custom_reason:
        full_reason += f" - {custom_reason}"
    
    review.mark_as_reported(full_reason)
    
    messages.success(request, "L'avis a été signalé à notre équipe de modération. Merci !")
    return redirect('shop:product_detail', id=review.product.id, slug=review.product.slug)

# ✅ VUES POUR LES CODES PROMO

@require_POST
def apply_coupon(request):
    """Applique un code promo au panier"""
    cart = _get_cart(request)
    form = CouponApplyForm(request.POST)
    
    if form.is_valid():
        code = form.cleaned_data['code']
        
        try:
            coupon = Coupon.objects.get(code=code, active=True)
            is_valid, message = coupon.is_valid(request.user if request.user.is_authenticated else None, cart)
            
            if is_valid:
                # Stocker le code promo dans la session
                request.session['coupon_id'] = coupon.id
                request.session['coupon_code'] = coupon.code
                
                # ✅ CORRECTION : Convertir en Decimal avant stockage
                if coupon.discount_type == 'free_shipping':
                    discount_amount = Decimal('0')
                    discount_message = "🎉 Livraison gratuite appliquée !"
                else:
                    discount_amount = coupon.calculate_discount(cart.get_total_price())
                    discount_message = f"🎉 Réduction de {discount_amount} € appliquée !"
                
                # ✅ CORRECTION : Stocker comme string pour éviter les problèmes de sérialisation
                request.session['discount_amount'] = str(float(discount_amount))
                request.session['coupon_type'] = coupon.discount_type
                
                messages.success(request, f"{discount_message} Code: {coupon.code}")
            else:
                # Supprimer le code invalide de la session
                clear_coupon_session(request)
                messages.error(request, f"❌ {message}")
                
        except Coupon.DoesNotExist:
            clear_coupon_session(request)
            messages.error(request, "❌ Code promo invalide.")
    
    return redirect('shop:cart_detail')

@csrf_protect
@require_POST
def remove_coupon(request):
    """Supprime le code promo appliqué"""
    clear_coupon_session(request)
    messages.info(request, "Code promo retiré.")
    return redirect('shop:cart_detail')

def clear_coupon_session(request):
    """Nettoie les données de coupon de la session"""
    session_keys = ['coupon_id', 'coupon_code', 'discount_amount', 'coupon_type']
    for key in session_keys:
        if key in request.session:
            del request.session[key]
    if 'coupon_id' in request.session:
        del request.session['coupon_id']
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
    if 'discount_amount' in request.session:
        del request.session['discount_amount']
    if 'coupon_type' in request.session:
        del request.session['coupon_type']

from decimal import Decimal

def _get_cart_with_discount(request):
    """Récupère le panier avec les informations de réduction"""
    cart = _get_cart(request)
    
    # ✅ CORRECTION : Convertir les float en Decimal
    discount_amount = request.session.get('discount_amount', 0)
    # Convertir float en Decimal si nécessaire
    if isinstance(discount_amount, float):
        discount_amount = Decimal(str(discount_amount))
    else:
        discount_amount = Decimal(discount_amount)
    
    # Ajouter les informations de réduction au contexte du panier
    cart.coupon_code = request.session.get('coupon_code', None)
    cart.discount_amount = discount_amount
    cart.coupon_type = request.session.get('coupon_type', None)
    
    # ✅ CORRECTION : Utiliser Decimal pour tous les calculs
    total_price = Decimal(str(cart.get_total_price())) if cart.get_total_price() else Decimal('0')
    
    # Calculer le total après réduction
    cart.total_after_discount = max(total_price - discount_amount, Decimal('0'))
    
    # Calculer les frais de livraison
    if cart.coupon_type == 'free_shipping':
        cart.shipping_cost = Decimal('0')
    else:
        # Logique de calcul des frais de livraison
        if total_price < Decimal('50'):
            cart.shipping_cost = Decimal('4.99')
        else:
            cart.shipping_cost = Decimal('0')
    
    cart.final_total = cart.total_after_discount + cart.shipping_cost
    
    return cart