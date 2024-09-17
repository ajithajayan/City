from django.db import models
from django.utils import timezone
import datetime
from decimal import Decimal
from django.dispatch import receiver
from django.db.models.signals import post_save


class NatureGroup(models.Model): # This gorup as main group
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class MainGroup(models.Model):  # This group as sub_group
    name = models.CharField(max_length=100, unique=True)
    nature_group = models.ForeignKey(NatureGroup, on_delete=models.CASCADE, related_name='main_groups')

    def __str__(self):
        return self.name

class Ledger(models.Model):
    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15, blank=True, null=True)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date = models.DateField(default=datetime.date.today)     
    group = models.ForeignKey(MainGroup, on_delete=models.CASCADE, related_name='ledgers')
    debit_credit = models.CharField(max_length=6, choices=[('DEBIT', 'Debit'), ('CREDIT', 'Credit')], blank=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    DEBIT = 'debit'
    CREDIT = 'credit'
    
    DEBIT_CREDIT_CHOICES = [
        (DEBIT, 'Debit'),
        (CREDIT, 'Credit'),
    ]
    # TRANSACTION_CHOICES = [
    #     ('payin', 'Payin'),
    #     ('payout', 'Payout'),
    # ]
    # transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE, related_name='ledger_transactions')  
    particulars = models.ForeignKey(Ledger, on_delete=models.CASCADE, related_name='particulars_transactions') 
    date = models.DateField()
    debit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)
    voucher_no = models.PositiveIntegerField()  
    ref_no = models.CharField(max_length=15, blank=True, null=True)
    debit_credit = models.CharField(
        max_length=10,
        choices=DEBIT_CREDIT_CHOICES
    )

    def __str__(self):
        return f"{self.ledger.name} - {self.date} - Voucher No: {self.voucher_no}"

    def save(self, *args, **kwargs):
        latest_transaction = Transaction.objects.filter(ledger=self.ledger).order_by('-date', '-id').first()
        
        if latest_transaction:
            previous_balance = latest_transaction.balance_amount
        else:
            previous_balance = Decimal('0.00')  
        
        was_negative = previous_balance < 0
        previous_balance = abs(previous_balance)  
        
        if self.debit_credit == self.DEBIT:
            self.balance_amount = previous_balance + self.debit_amount
        elif self.debit_credit == self.CREDIT:
            self.balance_amount = previous_balance - self.credit_amount
        
        if was_negative:
            self.balance_amount = -abs(self.balance_amount)
        
        super().save(*args, **kwargs)


class IncomeStatement(models.Model):
    SALES = 'Sales'
    INDIRECT_INCOME = 'Indirect Income'

    INCOME_TYPE_CHOICES = [
        (SALES, 'Sales'),
        (INDIRECT_INCOME, 'Indirect Income'),
        # Add other types as needed
    ]

    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE, related_name='income_statements')
    income_type = models.CharField(max_length=20, choices=INCOME_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.ledger.name} - {self.income_type} - {self.amount}"


class BalanceSheet(models.Model):
    ASSET = 'Asset'
    LIABILITY = 'Liability'

    BALANCE_TYPE_CHOICES = [
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        # Add other types as needed
    ]

    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE, related_name='balance_sheets')
    balance_type = models.CharField(max_length=20, choices=BALANCE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.ledger.name} - {self.balance_type} - {self.amount}"

#ShareManagement Section
class ShareUsers(models.Model):
    CATEGORY_CHOICES = [
        ('partners', 'Partners'),
        ('managements', 'Managements'),
    ]

    name = models.CharField(max_length=255)
    mobile_no = models.CharField(max_length=15)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)
    profitlose_share =  models.DecimalField(max_digits=5, decimal_places=2)
    address = models.TextField()

    def __str__(self):
        return self.name


#ShareManagement Section
class ProfitLossShareTransaction(models.Model):
    PROFIT_LOSS_CHOICES = [
        ('profit', 'Profit'),
        ('lose', 'Lose'),
    ]
    
    created_date = models.DateTimeField(auto_now_add=True)
    transaction_no = models.CharField(max_length=100, unique=True)
    period_from = models.DateField()
    period_to = models.DateField()
    total_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=PROFIT_LOSS_CHOICES, blank=True) 
    profit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    loss_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    def __str__(self):
        return f'Transaction {self.transaction_no} ({self.created_date})'

class ShareUserTransaction(models.Model):
    PROFIT_LOSS_CHOICES = [
        ('profit', 'Profit'),
        ('lose', 'Lose'),
    ]
    transaction = models.ForeignKey(ProfitLossShareTransaction, related_name='share_user_transactions', on_delete=models.CASCADE)
    share_user = models.ForeignKey(ShareUsers, related_name='share_user_transactions', on_delete=models.CASCADE)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    profit_lose = models.CharField(max_length=10, choices=PROFIT_LOSS_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    percentage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f'{self.share_user.name} - {self.transaction.transaction_no}'

class SharePaymentHistory(models.Model):
    share_user_transaction = models.ForeignKey(
        'ShareUserTransaction',
        related_name='payment_histories',
        on_delete=models.CASCADE
    )
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(blank=True, null=True)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Payment History ID {self.id} for Transaction ID {self.share_user_transaction.id}"

@receiver(post_save, sender=SharePaymentHistory)
def update_share_user_transaction(sender, instance, **kwargs):
    share_user_transaction = instance.share_user_transaction
    if share_user_transaction:
        # Subtract the paid amount from the balance amount
        share_user_transaction.balance_amount -= instance.paid_amount

        # Check if the balance amount is zero or less, and update is_paid status
        if share_user_transaction.balance_amount <= Decimal('0.00'):
            share_user_transaction.balance_amount = Decimal('0.00')
            share_user_transaction.is_paid = True

        # Save the updated ShareUserTransaction instance
        share_user_transaction.save()


class CashCountSheet(models.Model):
    TRANSACTION_CHOICES = [
        ('payin', 'Payin'),
        ('payout', 'Payout'),
    ]
    
    created_date = models.DateField()  # Date of the transaction
    voucher_number = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)  # Unique voucher number
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # Amount of the transaction
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)  # Type of transaction (Payin/Payout)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} - {self.amount}"

    def get_total_amount(self):
        """Calculate the total amount for this transaction."""
        return sum(item.amount for item in self.items.all())

    class Meta:
        verbose_name = "Cash Count Sheet"
        verbose_name_plural = "Cash Count Sheets"


class CashCountSheetItems(models.Model):
    created_date = models.DateField()
    currency = models.PositiveIntegerField()
    nos = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    ref = models.ForeignKey(CashCountSheet, on_delete=models.CASCADE, related_name='items')

    def __str__(self):
        return f"{self.currency} - {self.nos} - {self.amount}"

