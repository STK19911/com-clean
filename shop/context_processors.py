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
    except:
        return {'cart': None}