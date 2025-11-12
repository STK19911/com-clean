from django.urls import path
from . import views
from . import urls_vendor  # ← Ton fichier vendeur

app_name = 'shop'

urlpatterns = [
    # ── PRODUITS ─────────────────────
    path('', views.product_list, name='product_list'),
    path('category/<slug:category_slug>/', views.product_list, name='product_list_by_category'),
    path('product/<int:id>/<slug:slug>/', views.product_detail, name='product_detail'),

    # ── PANIER ───────────────────────
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),

    # ── COMMANDES ────────────────────
    path('order/create/', views.order_create, name='order_create'),
    path('order/created/<int:order_id>/', views.order_created, name='order_created'),
    path('order/history/', views.order_history, name='order_history'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='remove_coupon'),

    # ── FAVORIS ──────────────────────
    path('favorites/', views.favorite_list, name='favorite_list'),
    path('favorites/toggle/<int:product_id>/', views.toggle_favorite, name='toggle_favorite'),

    # ── AVIS ─────────────────────────
    path('review/add/<int:product_id>/', views.add_review, name='add_review'),
    path('review/delete/<int:review_id>/', views.delete_review, name='delete_review'),
    path('review/<int:review_id>/report/', views.report_review, name='report_review'),

    # ── AUTH ─────────────────────────
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    
    # ▼▼▼ LIGNES DE CONFIRMATION SUPPRIMÉES (CORRECTION) ▼▼▼
    # path('confirm-email/<uuid:token>/', views.confirm_email_view, name='confirm_email'),
    # path('admin/confirm-email/<int:user_id>/', views.admin_confirm_email, name='admin_confirm_email'),
    # path('resend-confirmation/', views.resend_confirmation_email, name='resend_confirmation'),
    # ▲▲▲ FIN SUPPRESSION ▲▲▲
]

# ── AJOUT DES URLS VENDEUR ───────
urlpatterns += urls_vendor.urlpatterns