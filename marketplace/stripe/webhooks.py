# stripe/webhooks.py (à créer)
import stripe
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from users.models import User
import json

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Webhook pour synchroniser les événements Stripe."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = 'whsec_YOUR_WEBHOOK_SECRET'  # À mettre en variable d'env
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")
    
    # Gérer l'événement customer.created
    if event['type'] == 'customer.created':
        handle_customer_created(event)
    if event['type'] == 'charge.dispute.created':
        handle_chargeback(event)
    if event['type'] == 'payment_intent.succeeded':
        handle_payment_succeeded(event)
    elif event['type'] == 'payment_intent.payment_failed':
        handle_payment_failed(event)
    
    return HttpResponse(status=200)

def handle_customer_created(event):
    """Gère la création d'un customer Stripe."""
    customer = event['data']['object']
    email = customer['email']
    stripe_customer_id = customer['id']
    
    try:
        # Trouver l'utilisateur par email et mettre à jour
        user = User.objects.get(email=email, stripe_user_id__isnull=True)
        user.stripe_user_id = stripe_customer_id
        user.save()
        
        print(f"✅ User {email} synchronisé avec Stripe customer {stripe_customer_id}")
    except User.DoesNotExist:
        print(f"⚠️ Aucun utilisateur trouvé pour {email}")

def handle_payment_succeeded(event):
    """Confirme le paiement d'une commande."""
    payment_intent = event['data']['object']
    
    # Récupérer l'ID de commande depuis les métadonnées
    order_id = payment_intent['metadata'].get('order_id')
    if not order_id:
        return
    
    try:
        from shop.models import Order
        order = Order.objects.get(id=order_id)
        
        # Confirmer la commande
        order.status = 'processing'  # Paiement confirmé
        order.save()
        
        print(f"✅ Commande {order_id} confirmée - Paiement reçu")
    except Order.DoesNotExist:
        print(f"⚠️ Commande {order_id} introuvable")

def handle_payment_failed(event):
    """Annule une commande en cas d'échec de paiement."""
    payment_intent = event['data']['object']
    order_id = payment_intent['metadata'].get('order_id')
    
    if not order_id:
        return
        
    try:
        from shop.models import Order
        order = Order.objects.get(id=order_id)
        
        # Annuler la commande et remettre le stock
        order.cancel_order()  # Utilise votre méthode existante
        
        print(f"❌ Commande {order_id} annulée - Paiement échoué")
    except Order.DoesNotExist:
        print(f"⚠️ Commande {order_id} introuvable")

def handle_chargeback(event):
    """Gère les chargebacks/contestations."""
    dispute = event['data']['object']
    charge_id = dispute['charge']
    
    # Récupérer le Payment Intent lié
    try:
        charge = stripe.Charge.retrieve(charge_id)
        payment_intent_id = charge['payment_intent']
        
        # Trouver la commande via métadonnées
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        order_id = payment_intent['metadata'].get('order_id')
        
        if order_id:
            from shop.models import Order
            order = Order.objects.get(id=order_id)
            
            # Marquer comme contestée
            order.status = 'disputed'  # 🆕 Nouveau statut à ajouter
            order.save()
            
            # 🚨 Alerter l'équipe
            print(f"🚨 ALERTE: Commande {order_id} contestée - Montant: {dispute['amount']/100}€")
            
    except Exception as e:
        print(f"Erreur traitement chargeback: {e}")