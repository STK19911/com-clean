# shop/context_processors.py
from .models import Cart

def cart_context(request):
    """Ajoute le panier à tous les templates"""
    try:
        cart = None
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
        return {'cart': cart}
    except Exception:
        return {'cart': None}


def vendor_status(request):
    """Ajoute un flag sûr indiquant si l'utilisateur est un vendeur approuvé.

    Retourne {'is_vendor_approved': True/False} — sûr même si l'utilisateur n'a pas de
    vendor_profile (évite RelatedObjectDoesNotExist dans les templates).
    """
    try:
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return {'is_vendor_approved': False}

        vendor = getattr(user, 'vendor_profile', None)
        return {'is_vendor_approved': bool(vendor and getattr(vendor, 'is_approved', False))}
    except Exception:
        return {'is_vendor_approved': False}