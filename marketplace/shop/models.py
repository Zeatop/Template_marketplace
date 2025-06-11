from django.db import models
from colors import Colors
import datetime
from decimal import Decimal
from users.models import User

class Client(models.Model):
    """Modèle représentant un client."""
    
    name = models.CharField(max_length=255, verbose_name="Nom")
    mail = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'client'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @classmethod
    def create_client(cls, client_infos: dict):
        """Crée un nouveau client avec les informations fournies."""
        client = cls.objects.create(
            name=client_infos["name"], 
            mail=client_infos["mail"], 
            phone=client_infos["phone"]
        )
        return client
    
    def update_phone(self, phone):
        """Met à jour le numéro de téléphone du client."""
        self.phone = phone
        self.save()
    
    def update_mail(self, mail):
        """Met à jour l'email du client."""
        self.mail = mail
        self.save()

class Contract(models.Model):
    """Modèle représentant un contrat."""
    
    STATE_CHOICES = [
        ('draft', 'Brouillon'),
        ('signed', 'Signé'),
        ('cancelled', 'Annulé'),
        ('completed', 'Terminé'),
    ]
    
    client = models.ForeignKey(
        Client, 
        on_delete=models.CASCADE, 
        related_name='contracts',
        verbose_name="Client"
    )
    commercial = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='contracts',
        verbose_name="Commercial"
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Montant total"
    )
    rest_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Montant restant"
    )
    state = models.CharField(
        max_length=20, 
        choices=STATE_CHOICES, 
        default='draft',
        verbose_name="État"
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'contract'
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-date_created']
    
    def __str__(self):
        return f'Contrat n°{self.id} - {self.client.name}'

    @classmethod
    def create_contract(cls, contract_dict: dict):
        """Crée un nouveau contrat avec les informations fournies."""
        try:
            contract = cls.objects.create(
                client=contract_dict["client"], 
                commercial=contract_dict["commercial"], 
                total_amount=contract_dict["total_amount"],
                rest_amount=contract_dict["rest_amount"], 
                state=contract_dict.get("state", "draft")
            )
            return contract
        except Exception as e:
            print(Colors.error(f"Une erreur est survenue lors de la création du contrat : {e}"))
            return None
    
    def update_contract_state(self, state):
        """Met à jour l'état du contrat."""
        if state in [choice[0] for choice in self.STATE_CHOICES]:
            self.state = state
            self.save()
        else:
            raise ValueError(f"État invalide: {state}")
    
    def update_rest_amount(self, amount):
        """Met à jour le montant restant du contrat."""
        try:
            if isinstance(self.rest_amount, float):
                self.rest_amount = float(self.rest_amount) - float(amount)
            else:
                self.rest_amount = self.rest_amount - Decimal(str(amount))
            
            # S'assurer que le montant restant ne devient pas négatif
            if self.rest_amount < 0:
                self.rest_amount = Decimal('0.00')
            
            self.save()
        except Exception as e:
            print(Colors.error(f"Erreur lors de la mise à jour du montant restant : {e}"))
    
    @property
    def is_paid(self):
        """Vérifie si le contrat est entièrement payé."""
        return self.rest_amount == 0
    
    @property
    def paid_amount(self):
        """Calcule le montant déjà payé."""
        return self.total_amount - self.rest_amount

class Event(models.Model):
    """Modèle représentant un événement."""
    
    contract = models.ForeignKey(
        Contract, 
        on_delete=models.CASCADE, 
        related_name='events',
        verbose_name="Contrat"
    )
    client = models.ForeignKey(
        Client, 
        on_delete=models.CASCADE, 
        related_name='events',
        verbose_name="Client"
    )
    name = models.CharField(max_length=255, unique=True, verbose_name="Nom")
    event_start = models.DateTimeField(verbose_name="Début de l'événement")
    event_end = models.DateTimeField(verbose_name="Fin de l'événement")
    logistic_contact = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='events', 
        null=True, 
        blank=True,
        verbose_name="Contact logistique"
    )
    location = models.CharField(max_length=255, verbose_name="Lieu")
    attendees = models.PositiveIntegerField(verbose_name="Nombre de participants")
    notes = models.TextField(null=True, blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'event'
        verbose_name = 'Événement'
        verbose_name_plural = 'Événements'
        ordering = ['event_start']
    
    def __str__(self):
        return self.name
    
    @classmethod
    def create_event(cls, contract_infos: dict):
        """Crée un nouvel événement avec les informations fournies."""
        try:
            event_data = {
                'contract': contract_infos["contract"],
                'client': contract_infos["client"],
                'event_start': contract_infos["event_start"],
                'event_end': contract_infos["event_end"],
                'name': contract_infos["name"],
                'location': contract_infos["location"],
                'attendees': contract_infos["attendees"],
                'notes': contract_infos.get("notes", "")
            }
            
            if "logistic_contact" in contract_infos and contract_infos["logistic_contact"]:
                event_data['logistic_contact'] = contract_infos["logistic_contact"]
            
            event = cls.objects.create(**event_data)
            return event
        except Exception as e:
            print(Colors.error(f"Une erreur est survenue lors de la création de l'évènement : {e}\nVeuillez réessayer."))
            return None
    
    def add_support(self, logistic_contact):
        """Ajoute un contact logistique à l'événement."""
        try:
            self.logistic_contact = logistic_contact
            self.save()
            return True
        except Exception as e:
            print(Colors.error(f"Erreur lors de l'ajout du support à l'évènement: {e}"))
            return None
    
    def remove_support(self):
        """Supprime le contact logistique de l'événement."""
        self.logistic_contact = None
        self.save()
    
    @property
    def duration(self):
        """Calcule la durée de l'événement."""
        return self.event_end - self.event_start
    
    @property
    def is_past(self):
        """Vérifie si l'événement est passé."""
        return self.event_end < datetime.datetime.now()
    
    @property
    def is_ongoing(self):
        """Vérifie si l'événement est en cours."""
        now = datetime.datetime.now()
        return self.event_start <= now <= self.event_end
    
    @property
    def is_upcoming(self):
        """Vérifie si l'événement est à venir."""
        return self.event_start > datetime.datetime.now()