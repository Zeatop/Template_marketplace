from django.db import models
import stripe
from rest_framework.response import Response
# Create your models here.


class StripeManager():

    STRIPE_TEST_ACCOUNT_ID = 'acct_1RdRjNRXyOM8gdvO'
    stripe.api_key = 'sk_test_YOUR_PLATFORM_SECRET_KEY'

    # 🆕 MÉTHODES UTILITAIRES CONCERNANT LES CUSTOMERS
     
    @staticmethod
    def create_or_retrieve_customer(email, name, stripe_account_id):
        print(f"\n--- 1. Création/Récupération du client '{email}' sur le compte connecté '{stripe_account_id}' ---")
        try:
            # Tenter de trouver un client existant avec cet email sur le compte connecté
            customers = stripe.Customer.list(
                email=email,
                limit=1,
                stripe_account=stripe_account_id # IMPORTANT : Cibler le compte connecté
            )
            if not customers.data:
                customer = stripe.Customer.create(
                    email=email,
                    name=name,
                    stripe_account=stripe_account_id # IMPORTANT : Cibler le compte connecté
                    )
            else:
                customer = customers.data[0]     
            return customer
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du client : {e}")
            return None
        
    @staticmethod
    def update_customer(customer_id, data, stripe_account_id):
        """Met à jour un customer Stripe existant."""
        print(f"\n--- Mise à jour du customer Stripe '{customer_id}' ---")
        
        # Mapper les champs Django vers Stripe
        stripe_data = {}
        
        if 'email' in data:
            stripe_data['email'] = data['email']
        
        if 'name' in data:
            stripe_data['name'] = f"{data['name']} {data['surname']}"
        
        if 'phone' in data:
            stripe_data['phone'] = data['phone']
        
        # Gestion de l'adresse
        if 'address' in data and data['address']:
            stripe_data['address'] = {
                'line1': data['address'].get('street', ''),
                'city': data['address'].get('city', ''),
                'postal_code': data['address'].get('postal_code', ''),
                'country': data['address'].get('country', '')
            }
        
        try:
            customer = stripe.Customer.modify(
                customer_id,
                **stripe_data,
                stripe_account=stripe_account_id
            )
            print(f"Customer mis à jour : {customer.id}")
            return customer
            
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la mise à jour du customer : {e}")
            raise

    @staticmethod
    def delete_customer(customer_id, stripe_account_id):
        """Supprime un customer Stripe."""
        print(f"\n--- Suppression du customer Stripe '{customer_id}' ---")
        try:
            stripe.Customer.delete(
                customer_id,
                stripe_account=stripe_account_id
            )
            print(f"Customer supprimé : {customer_id}")
            return True
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la suppression du customer : {e}")
            return False
    
    
    # 🆕 MÉTHODES UTILITAIRES CONCERNANT LES PRODUCTS ET PRICES
    
    @staticmethod
    def create_or_retrieve_product(name, description, stripe_account_id):
        print(f"\n--- Création/Récupération du produit '{name}' sur le compte connecté '{stripe_account_id}' ---")
        try:
            # Tenter de trouver un produit existant avec ce nom
            products = stripe.Product.list(
                limit=1,
                active=True,
                name=name,
                stripe_account=stripe_account_id # Cibler le compte connecté
            )
            if products.data:
                product = products.data[0]
                print(f"Produit existant récupéré : {product.id}")
            else:
                # Créer un nouveau produit si non trouvé
                product = stripe.Product.create(
                    name=name,
                    description=description,
                    stripe_account=stripe_account_id # Cibler le compte connecté
                )
                print(f"Nouveau produit créé : {product.id}")
            return product
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du produit : {e}")
            return None

    @staticmethod
    def update_product(product_id, data, stripe_account_id):
        print(f"\n--- Mise à jour du produit '{product_id}' sur le compte connecté '{stripe_account_id}' ---")

        stripe_data = {}

        if 'description' in data:
                stripe_data['description'] = data['description']
            
        if 'name' in data:
            stripe_data['name'] = data['name']

        try:

            
            product = stripe.Product.modify(
                product_id,
                **stripe_data,
                stripe_account=stripe_account_id
            )
            print(f"Produit mis à jour : {product.id}")
            return product
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la modification du produit : {e}")
            return None
    
    @staticmethod
    def delete_product(product_id, stripe_account_id):
        print(f"\n--- Suppression du produit '{product_id}' sur le compte connecté '{stripe_account_id}' ---")
        try:
            product = stripe.Product.modify(
                product_id,
                active=False,  # Stripe ne permet pas de supprimer un produit, on le désactive
                stripe_account=stripe_account_id
            )
            print(f"Produit désactivé : {product.id}")
            return product
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la désactivation du produit : {e}")
            return None
    
    @staticmethod
    def create_or_retrieve_price(product_id, unit_amount, currency, stripe_account_id, nickname="Standard Price"):
        print(f"\n--- Création/Récupération du prix pour le produit '{product_id}' avec un montant de {unit_amount} {currency} sur le compte connecté '{stripe_account_id}' ---")
        try:
            # Tenter de trouver un prix existant pour ce produit et ce montant
            # Il n'y a pas de recherche directe par unit_amount + product_id via list,
            # donc nous allons lister les prix pour le produit et filtrer manuellement.
            prices = stripe.Price.list(
                product=product_id,
                currency=currency,
                nickname=nickname, # Filtrer par nom por Standard Price et Promo Price
                limit=100, # Augmenter la limite pour s'assurer de récupérer tous les prix
                active=True,
                stripe_account=stripe_account_id if stripe_account_id else None # Cibler le compte connecté si fourni
            )
            
            found_price = None
            for price in prices.data:
                if price.unit_amount == unit_amount and price.currency == currency:
                    found_price = price
                    break
            
            if found_price:
                price = found_price
                print(f"Prix existant récupéré : {price.id}")
            else:
                # Créer un nouveau prix si non trouvé
                price = stripe.Price.create(
                    product=product_id,
                    unit_amount=unit_amount, # Montant en centimes
                    currency=currency,
                    nickname=nickname, # Un nom optionnel pour le prix (ex: "Prix standard")
                    stripe_account=stripe_account_id if stripe_account_id else None # Cibler le compte connecté si fourni
                )
                print(f"Nouveau prix créé : {price.id}")
            return price
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du prix : {e}")
            return None

    @staticmethod
    def get_product_price(name, description, stripe_account_id, unit_amount, currency):
        print(f"\n--- Récupération du prix pour le produit '{name}' sur le compte connecté '{stripe_account_id}' ---")
        # Étape 1 : Créer ou récupérer le produit
        product = StripeManager.create_or_retrieve_product(name, description, stripe_account_id)
        if not product:
            return None
        
        # Étape 2 : Créer ou récupérer le prix pour ce produit
        price = StripeManager.create_or_retrieve_price(product.id, unit_amount, currency, stripe_account_id)
        
        return price

    @staticmethod
    def delete_price(price_id, stripe_account_id):
        print(f"\n--- Suppression du prix '{price_id}' sur le compte connecté '{stripe_account_id}' ---")
        try:
            price = stripe.Price.modify(
                price_id,
                active=False,  # Stripe ne permet pas de supprimer un prix, on le désactive
                stripe_account=stripe_account_id
            )
            print(f"Prix désactivé : {price.id}")
            return price
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la désactivation du prix : {e}")
            return None
    #🆕 MÉTHODES UTILITAIRES CONCERNANT LES PAIEMENTS

    @staticmethod
    def attach_payment_method_to_customer(customer_id, payment_method_id, stripe_account_id):
        print(f"\n--- 2. Attachement de la Payment Method '{payment_method_id}' au client '{customer_id}' sur le compte connecté ---")
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
                stripe_account=stripe_account_id # IMPORTANT : Cibler le compte connecté
            )
            print(f"Payment Method '{payment_method.id}' attachée au client '{customer_id}'.")
            return payment_method
        except stripe.error.StripeError as e:
            print(f"Erreur lors de l'attachement de la Payment Method : {e}")
            return None
    
    @staticmethod
    def create_payment_intent_for_order(customer_id, amount, order_id, stripe_account_id):
        """Crée un Payment Intent avec métadonnées pour une commande."""
        print(f"\n--- Création Payment Intent pour commande {order_id or 'à venir'} ---")
        try:
            # 🆕 Métadonnées adaptatives selon si on a déjà l'order_id ou pas
            metadata = {
                'source': 'marketplace',
                'customer_id': customer_id
            }
            
            # Ajouter l'order_id seulement s'il existe (pour éviter "None")
            if order_id:
                metadata['order_id'] = str(order_id)
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,  # Montant en centimes
                currency='eur',
                customer=customer_id,
                metadata=metadata,  # 🔧 Métadonnées conditionnelles
                # Configuration paiement
                confirmation_method='manual',
                confirm=False,  # Ne pas confirmer automatiquement
                stripe_account=stripe_account_id
            )
            
            print(f"✅ Payment Intent créé : {payment_intent.id}")
            if order_id:
                print(f"   Order ID dans metadata : {payment_intent.metadata.get('order_id')}")
            else:
                print(f"   Order ID sera ajouté ultérieurement")
            
            return payment_intent
            
        except stripe.error.StripeError as e:
            print(f"❌ Erreur création Payment Intent : {e}")
            return None

    @staticmethod
    def update_payment_intent_metadata(payment_intent_id, order_id, stripe_account_id):
        """Met à jour les métadonnées d'un Payment Intent avec l'order_id."""
        try:
            payment_intent = stripe.PaymentIntent.modify(
                payment_intent_id,
                metadata={'order_id': str(order_id)},
                stripe_account=stripe_account_id
            )
            print(f"✅ Métadonnées mises à jour : PI {payment_intent_id} → Order {order_id}")
            return payment_intent
        except stripe.error.StripeError as e:
            print(f"⚠️ Erreur mise à jour métadonnées : {e}")
            return None
    
    @staticmethod
    def create_direct_payment_intent(customer_id, payment_method_id, amount, currency, description, stripe_account_id):
        print(f"\n--- 3. Création d'un Payment Intent pour une Direct Charge sur le compte connecté '{stripe_account_id}' ---")
        try:
            # Créer le Payment Intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,          # Montant en centimes (ex: 1000 pour 10.00 EUR)
                currency=currency,      # Devise (ex: 'eur', 'usd')
                customer=customer_id,   # L'ID du client Stripe
                payment_method=payment_method_id, # L'ID de la Payment Method
                off_session=False,      # Indique que le paiement est initié par le client
                confirm=True,           # Tenter de confirmer le paiement immédiatement
                description=description,
                # IMPORTANT : Utilisez 'stripe_account' pour que la charge soit effectuée sur le compte connecté
                stripe_account=stripe_account_id
            )
            print(f"Payment Intent créé/confirmé : {payment_intent.id}")
            print(f"Statut du Payment Intent : {payment_intent.status}")
            return payment_intent
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création du Payment Intent : {e}")
            print(f"Message d'erreur Stripe: {e.user_message if hasattr(e, 'user_message') else e}")
            return None
        
    @staticmethod
    def perform_payment(email, name, payment_method_id, amount, currency, description, stripe_account_id):
        print(f"\n--- 4. Démarrage du processus de paiement pour '{email}' ---")
        # Étape 1 : Créer ou récupérer le client
        customer = StripeManager.create_or_retrieve_customer(email, name, stripe_account_id)
        if not customer:
            return None
        
        # Étape 2 : Attacher la Payment Method au client
        payment_method = StripeManager.attach_payment_method_to_customer(customer.id, payment_method_id, stripe_account_id)
        if not payment_method:
            return None
        
        # Étape 3 : Créer le Payment Intent pour une Direct Charge
        payment_intent = StripeManager.create_direct_payment_intent(
            customer.id,
            payment_method.id,
            amount,
            currency,
            description,
            stripe_account_id
        )
        
        return payment_intent
    