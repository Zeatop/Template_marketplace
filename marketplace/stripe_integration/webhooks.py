# marketplace/stripe/webhooks.py - VERSION ROBUSTE COMPLÈTE

import stripe
import json
import logging
import traceback
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from users.models import User
from shop.models import Order, WebhookEvent
from constants import STRIPE_ACCOUNT_ID

# Configuration du logging
logger = logging.getLogger('stripe_webhooks')

# Configuration Stripe (à mettre en variables d'environnement)
STRIPE_WEBHOOK_SECRET = getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_your_secret_here')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Point d'entrée principal pour tous les webhooks Stripe.
    Implémente idempotence, gestion d'erreurs robuste et retry logic.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    # Logging de la requête entrante
    logger.info(f"Webhook reçu - IP: {request.META.get('REMOTE_ADDR')}, Size: {len(payload)} bytes")
    
    # 1. VALIDATION DE LA SIGNATURE STRIPE
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"Signature Stripe validée - Event: {event['id']} Type: {event['type']}")
        
    except ValueError as e:
        logger.error(f"Payload invalide: {e}")
        return HttpResponseBadRequest("Invalid payload")
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature invalide: {e}")
        return HttpResponseBadRequest("Invalid signature")
    
    # 2. VÉRIFICATION D'IDEMPOTENCE
    if WebhookEvent.is_already_processed(event['id']):
        logger.info(f"Événement {event['id']} déjà traité - Ignoré (idempotence)")
        return HttpResponse(status=200)
    
    # 3. CRÉATION DE L'ENREGISTREMENT WEBHOOK
    try:
        webhook_event, created = WebhookEvent.create_from_stripe_event(event)
        if not created:
            logger.warning(f"Événement {event['id']} existe déjà mais pas encore traité")
    except Exception as e:
        logger.error(f"Erreur création WebhookEvent: {e}")
        return HttpResponse(status=500)
    
    # 4. TRAITEMENT DE L'ÉVÉNEMENT
    return process_webhook_event(webhook_event)


def process_webhook_event(webhook_event):
    """
    Traite un événement webhook avec gestion d'erreurs complète.
    """
    event_id = webhook_event.stripe_event_id
    event_type = webhook_event.event_type
    event_data = webhook_event.event_data
    
    logger.info(f"Début traitement {event_type} - Event ID: {event_id}")
    
    # Marquer comme en cours de traitement
    webhook_event.mark_as_processing()
    
    try:
        with transaction.atomic():
            # Router vers le bon handler selon le type d'événement
            handler_map = {
                'customer.created': handle_customer_created,
                'payment_intent.succeeded': handle_payment_succeeded,
                'payment_intent.payment_failed': handle_payment_failed,
                'charge.dispute.created': handle_chargeback,
            }
            
            handler = handler_map.get(event_type)
            
            if handler:
                # Exécuter le handler spécifique
                result = handler(event_data, webhook_event)
                
                if result.get('success', True):
                    webhook_event.mark_as_success(result.get('message', 'Traitement réussi'))
                    logger.info(f"✅ {event_type} traité avec succès - {event_id}")
                else:
                    error_msg = result.get('error', 'Erreur inconnue')
                    webhook_event.mark_as_failed(error_msg, should_retry=result.get('should_retry', True))
                    logger.warning(f"⚠️ {event_type} échoué (will retry): {error_msg}")
            else:
                # Type d'événement non géré
                message = f"Type d'événement non géré: {event_type}"
                webhook_event.mark_as_success(message)  # Marquer comme success pour éviter les retries
                logger.info(f"ℹ️ {message}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        # Erreur critique non prévue
        error_msg = f"Erreur critique lors du traitement: {str(e)}"
        webhook_event.mark_as_failed(error_msg, should_retry=True)
        
        logger.error(f"❌ Erreur critique {event_type}: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Retourner 500 pour que Stripe retry automatiquement
        return HttpResponse(status=500)


# ========================================
# HANDLERS SPÉCIFIQUES PAR TYPE D'ÉVÉNEMENT
# ========================================

def handle_customer_created(event_data, webhook_event):
    """Gère la création d'un customer Stripe."""
    try:
        customer = event_data['data']['object']
        email = customer['email']
        stripe_customer_id = customer['id']
        
        webhook_event.add_log(f"Recherche utilisateur avec email: {email}")
        
        # Rechercher l'utilisateur correspondant
        user = User.objects.filter(
            email=email,
            stripe_user_id__isnull=True
        ).first()
        
        if user:
            user.stripe_user_id = stripe_customer_id
            user.save(update_fields=['stripe_user_id'])
            
            message = f"User {email} synchronisé avec Stripe customer {stripe_customer_id}"
            webhook_event.add_log(message, 'success')
            
            return {'success': True, 'message': message}
        else:
            message = f"Aucun utilisateur trouvé pour {email} (normal si customer créé manuellement)"
            webhook_event.add_log(message, 'info')
            
            return {'success': True, 'message': message}
            
    except Exception as e:
        error_msg = f"Erreur handle_customer_created: {str(e)}"
        webhook_event.add_log(error_msg, 'error')
        return {'success': False, 'error': error_msg, 'should_retry': True}


def handle_payment_succeeded(event_data, webhook_event):
    """Confirme le paiement d'une commande."""
    try:
        payment_intent = event_data['data']['object']
        payment_intent_id = payment_intent['id']
        
        webhook_event.add_log(f"Recherche commande avec Payment Intent: {payment_intent_id}")
        
        # 🔑 UTILISATION DU NOUVEAU CHAMP payment_intent_id
        order = Order.get_by_payment_intent(payment_intent_id)
        
        if not order:
            # Fallback sur les métadonnées si pas trouvé par payment_intent_id
            order_id = payment_intent.get('metadata', {}).get('order_id')
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    # Mettre à jour le payment_intent_id manquant
                    order.payment_intent_id = payment_intent_id
                    order.save(update_fields=['payment_intent_id'])
                    webhook_event.add_log(f"Payment Intent ID ajouté à la commande {order_id}")
                except Order.DoesNotExist:
                    pass
        
        if order:
            # Vérifier que la commande peut être confirmée
            if order.status == 'pending':
                order.status = 'processing'
                order.save(update_fields=['status', 'updated_at'])
                
                message = f"Commande {order.id} confirmée → status: processing"
                webhook_event.add_log(message, 'success')
                
                return {'success': True, 'message': message}
            else:
                message = f"Commande {order.id} déjà dans état: {order.status}"
                webhook_event.add_log(message, 'info')
                return {'success': True, 'message': message}
        else:
            error_msg = f"Aucune commande trouvée pour Payment Intent {payment_intent_id}"
            webhook_event.add_log(error_msg, 'warning')
            # Ne pas retry car la commande n'existe pas
            return {'success': False, 'error': error_msg, 'should_retry': False}
            
    except Exception as e:
        error_msg = f"Erreur handle_payment_succeeded: {str(e)}"
        webhook_event.add_log(error_msg, 'error')
        return {'success': False, 'error': error_msg, 'should_retry': True}


def handle_payment_failed(event_data, webhook_event):
    """Annule une commande en cas d'échec de paiement."""
    try:
        payment_intent = event_data['data']['object']
        payment_intent_id = payment_intent['id']
        last_payment_error = payment_intent.get('last_payment_error', {})
        failure_reason = last_payment_error.get('message', 'Raison inconnue')
        
        webhook_event.add_log(f"Échec paiement: {failure_reason}")
        
        # 🔑 UTILISATION DU NOUVEAU CHAMP payment_intent_id
        order = Order.get_by_payment_intent(payment_intent_id)
        
        if not order:
            # Fallback sur les métadonnées
            order_id = payment_intent.get('metadata', {}).get('order_id')
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                except Order.DoesNotExist:
                    pass
        
        if order:
            # Utiliser la méthode d'annulation existante qui remet le stock
            if order.cancel_order():
                message = f"Commande {order.id} annulée - Stock remis en place"
                webhook_event.add_log(message, 'success')
                return {'success': True, 'message': message}
            else:
                error_msg = f"Impossible d'annuler commande {order.id} - Statut: {order.status}"
                webhook_event.add_log(error_msg, 'warning')
                return {'success': False, 'error': error_msg, 'should_retry': False}
        else:
            error_msg = f"Aucune commande trouvée pour Payment Intent {payment_intent_id}"
            webhook_event.add_log(error_msg, 'warning')
            return {'success': False, 'error': error_msg, 'should_retry': False}
            
    except Exception as e:
        error_msg = f"Erreur handle_payment_failed: {str(e)}"
        webhook_event.add_log(error_msg, 'error')
        return {'success': False, 'error': error_msg, 'should_retry': True}


def handle_chargeback(event_data, webhook_event):
    """Gère les chargebacks/contestations."""
    try:
        dispute = event_data['data']['object']
        charge_id = dispute['charge']
        amount = dispute['amount'] / 100  # Convertir centimes → euros
        reason = dispute.get('reason', 'unknown')
        
        webhook_event.add_log(f"Chargeback détecté - Charge: {charge_id}, Montant: {amount}€, Raison: {reason}")
        
        # Récupérer le Payment Intent lié
        charge = stripe.Charge.retrieve(charge_id)
        payment_intent_id = charge.get('payment_intent')
        
        if not payment_intent_id:
            error_msg = "Pas de Payment Intent lié à cette charge"
            webhook_event.add_log(error_msg, 'warning')
            return {'success': False, 'error': error_msg, 'should_retry': False}
        
        # 🔑 UTILISATION DU NOUVEAU CHAMP payment_intent_id
        order = Order.get_by_payment_intent(payment_intent_id)
        
        if order:
            order.status = 'disputed'
            order.save(update_fields=['status', 'updated_at'])
            
            alert_message = (
                f"🚨 ALERTE CHARGEBACK!\n"
                f"Commande {order.id} marquée comme contestée\n"
                f"Montant: {amount}€ - Raison: {reason}\n"
                f"Charge ID: {charge_id}"
            )
            
            webhook_event.add_log(alert_message, 'critical')
            logger.critical(alert_message)
            
            # TODO: Ajouter ici l'envoi d'alertes (email, Slack, etc.)
            
            return {'success': True, 'message': f"Commande {order.id} marquée comme disputée"}
        else:
            error_msg = f"Aucune commande trouvée pour Payment Intent {payment_intent_id}"
            webhook_event.add_log(error_msg, 'warning')
            return {'success': False, 'error': error_msg, 'should_retry': False}
            
    except Exception as e:
        error_msg = f"Erreur handle_chargeback: {str(e)}"
        webhook_event.add_log(error_msg, 'error')
        return {'success': False, 'error': error_msg, 'should_retry': True}