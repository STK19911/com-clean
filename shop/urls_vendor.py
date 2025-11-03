# shop/urls_vendor.py
from django.urls import path
from . import views_vendor

app_name = 'shop'

urlpatterns = [
    path('vendor/', views_vendor.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/add/', views_vendor.vendor_add_product, name='vendor_add_product'),
    path('vendor/edit/<int:pk>/', views_vendor.vendor_edit_product, name='vendor_edit_product'),
    path('vendor/delete/<int:pk>/', views_vendor.vendor_delete_product, name='vendor_delete_product'),
]