# shop/views_vendor.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404
from .forms import VendorProductForm
from .models import Product  # Assure-toi que OrderItem est importé si besoin, mais pas ici

@login_required
def vendor_dashboard(request):
    if not hasattr(request.user, 'vendor_profile') or not request.user.vendor_profile.is_approved:
        messages.error(request, "⚠️ Votre boutique est en attente d’approbation.")
        return redirect('shop:product_list')
    
    products = request.user.vendor_profile.products.all().order_by('-created')
    stats = {
        'total_products': products.count(),
        'in_stock': products.filter(stock__gt=0).count(),
        # ← Fix : Utilise 'orderitem_set' au lieu de 'order_items' (relation inverse par défaut)
        'total_sales': sum(p.orderitem_set.filter(order__paid=True).count() for p in products)
    }
    return render(request, 'shop/vendor/dashboard.html', {
        'products': products,
        'stats': stats,
        'shop': request.user.vendor_profile
    })

@login_required
def vendor_add_product(request):
    if not hasattr(request.user, 'vendor_profile') or not request.user.vendor_profile.is_approved:
        raise Http404
    
    if request.method == 'POST':
        form = VendorProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user.vendor_profile
            product.save()
            messages.success(request, "✨ Produit publié avec succès !")
            return redirect('shop:vendor_dashboard')
        else:
            messages.error(request, "❌ Erreur lors de la publication. Vérifiez les champs.")
    else:
        form = VendorProductForm()
    
    return render(request, 'shop/vendor/add_product.html', {
        'form': form,
        'shop': request.user.vendor_profile  # Pour le titre dynamique
    })

@login_required
def vendor_edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.user.vendor_profile)
    if request.method == 'POST':
        form = VendorProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Produit mis à jour avec succès !")
            return redirect('shop:vendor_dashboard')
        else:
            messages.error(request, "❌ Erreur lors de la mise à jour.")
    else:
        form = VendorProductForm(instance=product)
    
    return render(request, 'shop/vendor/edit_product.html', {
        'form': form,
        'product': product,
        'shop': request.user.vendor_profile
    })

@login_required
def vendor_delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.user.vendor_profile)
    if request.method == 'POST':
        product_name = product.name  # Sauvegarder pour le message
        product.delete()
        messages.success(request, f"🗑️ {product_name} supprimé avec succès.")
    return redirect('shop:vendor_dashboard')