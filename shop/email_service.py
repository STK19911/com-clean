from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_confirmation_email(user):
    """Envoie un email de confirmation de compte"""
    subject = 'Confirmez votre compte MonShop'
    
    # Lien de confirmation
    confirmation_url = f"{settings.SITE_URL}/confirm-email/{user.profile.confirmation_token}/"
    
    # Contenu HTML de l'email
    html_message = render_to_string('shop/auth/confirmation_email.html', {
        'user': user,
        'confirmation_url': confirmation_url,
    })
    
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )

def send_welcome_email(user):
    """Envoie un email de bienvenue après confirmation"""
    subject = 'Bienvenue sur MonShop !'
    
    html_message = render_to_string('shop/auth/welcome_email.html', {
        'user': user,
    })
    
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )