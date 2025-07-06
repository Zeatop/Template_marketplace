from django.db import models
import stripe
# Create your models here.
class StripeManager(models.Manager):

    STRIPE_TEST_ACCOUNT_ID = 'acct_1RdRjNRXyOM8gdvO'
    stripe.api_key = 'sk_test_YOUR_PLATFORM_SECRET_KEY'

    @staticmethod
    def create_or_retrieve_customer(email, name, connected_account_id):
        print(f"\n--- 1. Création/Récupération du client '{email}' sur le compte connecté '{connected_account_id}' ---")
        try:
            # Tenter de trouver un client existant avec cet email sur le compte connecté
            customers = stripe.Customer.list(
                email=email,
                limit=1,
                stripe_account=connected_account_id # IMPORTANT : Cibler le compte connecté
            )
            if customers.data:
                customer = customers.data[0]
                print(f"Client existant récupéré : {customer.id}")
            else:
                # Créer un nouveau client si non trouvé
                customer = stripe.Customer.create(
                    email=email,
                    name=name,
                    description=f"Client pour le site e-commerce de {name}",
                    stripe_account=connected_account_id # IMPORTANT : Cibler le compte connecté
                )
                print(f"Nouveau client créé : {customer.id}")
            return customer
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du client : {e}")
            return None
    
    @staticmethod
    def attach_payment_method_to_customer(customer_id, payment_method_id, connected_account_id):
        print(f"\n--- 2. Attachement de la Payment Method '{payment_method_id}' au client '{customer_id}' sur le compte connecté ---")
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
                stripe_account=connected_account_id # IMPORTANT : Cibler le compte connecté
            )
            print(f"Payment Method '{payment_method.id}' attachée au client '{customer_id}'.")
            return payment_method
        except stripe.error.StripeError as e:
            print(f"Erreur lors de l'attachement de la Payment Method : {e}")
            return None
    
    @staticmethod
    def create_direct_payment_intent(customer_id, payment_method_id, amount, currency, description, connected_account_id):
        print(f"\n--- 3. Création d'un Payment Intent pour une Direct Charge sur le compte connecté '{connected_account_id}' ---")
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
                stripe_account=connected_account_id
            )
            print(f"Payment Intent créé/confirmé : {payment_intent.id}")
            print(f"Statut du Payment Intent : {payment_intent.status}")
            return payment_intent
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création du Payment Intent : {e}")
            print(f"Message d'erreur Stripe: {e.user_message if hasattr(e, 'user_message') else e}")
            return None
        
    @staticmethod
    def perform_payment(email, name, payment_method_id, amount, currency, description, connected_account_id):
        print(f"\n--- 4. Démarrage du processus de paiement pour '{email}' ---")
        # Étape 1 : Créer ou récupérer le client
        customer = StripeManager.create_or_retrieve_customer(email, name, connected_account_id)
        if not customer:
            return None
        
        # Étape 2 : Attacher la Payment Method au client
        payment_method = StripeManager.attach_payment_method_to_customer(customer.id, payment_method_id, connected_account_id)
        if not payment_method:
            return None
        
        # Étape 3 : Créer le Payment Intent pour une Direct Charge
        payment_intent = StripeManager.create_direct_payment_intent(
            customer.id,
            payment_method.id,
            amount,
            currency,
            description,
            connected_account_id
        )
        
        return payment_intent
    
    @staticmethod
    def create_or_retrieve_product(name, description, connected_account_id):
        print(f"\n--- Création/Récupération du produit '{name}' sur le compte connecté '{connected_account_id}' ---")
        try:
            # Tenter de trouver un produit existant avec ce nom
            products = stripe.Product.list(
                limit=1,
                active=True,
                name=name,
                stripe_account=connected_account_id # Cibler le compte connecté
            )
            if products.data:
                product = products.data[0]
                print(f"Produit existant récupéré : {product.id}")
            else:
                # Créer un nouveau produit si non trouvé
                product = stripe.Product.create(
                    name=name,
                    description=description,
                    stripe_account=connected_account_id # Cibler le compte connecté
                )
                print(f"Nouveau produit créé : {product.id}")
            return product
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du produit : {e}")
            return None

    @staticmethod
    def create_or_retrieve_price(product_id, unit_amount, currency, connected_account_id, nickname="Standard Price"):
        print(f"\n--- Création/Récupération du prix pour le produit '{product_id}' avec un montant de {unit_amount} {currency} sur le compte connecté '{connected_account_id}' ---")
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
                stripe_account=connected_account_id if connected_account_id else None # Cibler le compte connecté si fourni
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
                    stripe_account=connected_account_id if connected_account_id else None # Cibler le compte connecté si fourni
                )
                print(f"Nouveau prix créé : {price.id}")
            return price
        except stripe.error.StripeError as e:
            print(f"Erreur lors de la création/récupération du prix : {e}")
            return None

    @staticmethod
    def get_product_price(name, description, connected_account_id, unit_amount, currency):
        print(f"\n--- Récupération du prix pour le produit '{name}' sur le compte connecté '{connected_account_id}' ---")
        # Étape 1 : Créer ou récupérer le produit
        product = StripeManager.create_or_retrieve_product(name, description, connected_account_id)
        if not product:
            return None
        
        # Étape 2 : Créer ou récupérer le prix pour ce produit
        price = StripeManager.create_or_retrieve_price(product.id, unit_amount, currency, connected_account_id)
        
        return price