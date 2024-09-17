from datetime import timedelta
from django.db import models,transaction
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from transactions_app.models import MainGroup,Ledger
from .utils import default_time_period
import logging

logger = logging.getLogger(__name__)


class User(AbstractUser):
    ROLES = (
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("driver", "Driver"),
    )
    GENDERS = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    )
    role = models.CharField(max_length=10, choices=ROLES, blank=True, null=True)
    passcode = models.CharField(max_length=6, unique=True)
    gender = models.CharField(max_length=10, choices=GENDERS, null=True, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.role == "admin":
            self.is_staff = True
            self.is_superuser = True
        elif self.role == "staff":
            self.is_staff = True
            self.is_superuser = False
        elif self.role == "driver":
            self.is_staff = False
            self.is_superuser = False

        if self.password and not self.password.startswith("pbkdf2_"):
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

class LogoInfo(models.Model):
    company_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    location = models.CharField(max_length=255)
    office_number = models.CharField(max_length=20)
    main_logo = models.ImageField(upload_to='company_logos/')
    print_logo = models.ImageField(upload_to='company_logos/')

    def __str__(self):
        return self.company_name        


class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Dish(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="images/", default="default_dish_image.jpg")
    price = models.DecimalField(max_digits=6, decimal_places=2)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="dishes"
    )

    class Meta:
        verbose_name = "Dish"
        verbose_name_plural = "Dishes"
        ordering = ("-price",)

    def __str__(self):
        return self.name


class DishVariant(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name} ({self.dish.name})"


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
        ("delivered", "Delivered"),
    ]

    ORDER_TYPE_CHOICES = [
        ("takeaway", "Takeaway"),
        ("dining", "Dining"),
        ("delivery", "Delivery"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("cash-bank", "Cash and Bank"),
        ("credit", "Credit"),
    ]

    user = models.ForeignKey(User, related_name="orders", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    bill_generated = models.BooleanField(default=False)
    order_type = models.CharField(
        max_length=20, choices=ORDER_TYPE_CHOICES, default="dining"
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    cash_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    bank_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    invoice_number = models.CharField(max_length=20, blank=True)
    customer_name = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    customer_phone_number = models.CharField(max_length=12, blank=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_driver_id = models.IntegerField(null=True, blank=True)
    credit_user_id = models.IntegerField(null=True, blank=True)
    kitchen_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.id} - {self.created_at} - {self.order_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.invoice_number:
            self.invoice_number = (
                f"{self.id:04d}"  # Generates an invoice number with leading zeros
            )
            self.save(update_fields=["invoice_number"])

    def is_delivery_order(self):
        return self.order_type == "delivery"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    is_newly_added = models.BooleanField(default=False)
    variants = models.JSONField(default=list)

    def __str__(self):
        return f"{self.order.id} - {self.dish} - {self.quantity}"


class Bill(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="bills")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bills")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    billed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-billed_at",)

    def __str__(self):
        return f"Bill for order {self.order.id}"
    
    def delete(self, *args, **kwargs):
        logger.error(f"Bill {self.pk} is being deleted!")
        super().delete(*args, **kwargs)

    # def save(self, *args, **kwargs):
    #     if not self.pk:
    #         self.user = self.order.user
    #         self.order.bill_generated = True
    #         self.paid = True
    #         self.order.save()
    #     super().save(*args, **kwargs)


class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.message[:50]}..."


@receiver(post_save, sender=Order)
def create_notification_for_orders(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            message=f"New order created: Order #{instance.id} with a total amount of ${instance.total_amount}"
        )


@receiver(post_save, sender=Bill)
def create_notification_for_bills(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            message=f"New bill #{instance.id} generated for Order #{instance.order.id}"
        )


class Floor(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Table(models.Model):
    table_name = models.CharField(max_length=50)
    start_time = models.TimeField(default="00:00")
    end_time = models.TimeField(default="00:00")
    seats_count = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    floor = models.ForeignKey(Floor, related_name="tables", on_delete=models.CASCADE)
    is_ready = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.table_name} - {self.floor.name}"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    min_purchase_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.code

    def is_valid(self):
        """Check if the coupon is valid based on its date and usage limit."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now or self.end_date < now:
            return False
        if self.usage_limit is not None and self.usage_count >= self.usage_limit:
            return False
        return True

    def apply_discount(self, amount):
        """Apply the discount to a given amount."""
        if self.discount_percentage:
            return amount - (amount * self.discount_percentage / 100)
        if self.discount_amount:
            return amount - self.discount_amount
        return amount


class MessType(models.Model):
    MESS_TYPE_CHOICES = [
        ("breakfast_lunch_dinner", "Breakfast and Lunch and Dinner"),
        ("breakfast_lunch", "Breakfast and Lunch"),
        ("breakfast_dinner", "Breakfast and Dinner"),
        ("lunch_dinner", "Lunch and Dinner"),
    ]

    name = models.CharField(max_length=50, choices=MESS_TYPE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()


class Menu(models.Model):
    DAY_OF_WEEK_CHOICES = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]

    name = models.CharField(max_length=255)
    day_of_week = models.CharField(
        max_length=9, choices=DAY_OF_WEEK_CHOICES, blank=True, null=True
    )
    sub_total = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    is_custom = models.BooleanField(
        default=False
    )  # False for predefined, True for custom
    mess_type = models.ForeignKey(
        "MessType",
        related_name="menus",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_by = models.CharField(
        max_length=255, default="admin", null=True, blank=True
    )  # UUID for users, 'admin' for shop-created menus

    def __str__(self):
        return self.name

    def calculate_sub_total(self):
        menu_items = self.menu_items.all()
        total = sum(item.dish.price for item in menu_items) if menu_items else 0
        self.sub_total = total
        self.save()


class MenuItem(models.Model):
    MEAL_TYPE_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
    ]

    meal_type = models.CharField(
        max_length=20, choices=MEAL_TYPE_CHOICES, blank=True, null=True
    )
    menu = models.ForeignKey(Menu, related_name="menu_items", on_delete=models.CASCADE)
    dish = models.ForeignKey("Dish", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.dish.name}"


# Signal handler to update Menu's sub_total
@receiver(post_save, sender=MenuItem)
def update_menu_sub_total(sender, instance, **kwargs):
    menu = instance.menu
    menu.calculate_sub_total()


class Mess(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("cash-bank", "Cash and Bank"),
    ]

    customer_name = models.CharField(max_length=50, unique=True)
    mobile_number = models.CharField(max_length=15, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    mess_type = models.ForeignKey(
        MessType, related_name="messes", on_delete=models.CASCADE
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pending_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    menus = models.ManyToManyField(Menu, related_name="messes")
    cash_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )  # Add cahs_amount field on 21-08-2024
    bank_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )  # Add bank_amount field on 21-08-2024
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    initial_transaction_created = models.BooleanField(default=False)

    def calculate_total_amount(self, weeks):
        # Assuming the subtotal is the total for one week
        weekly_total = sum(menu.sub_total for menu in self.menus.all())
        return weekly_total * weeks

    # def save(self, *args, **kwargs):
    #     # Auto-calculate total amount before saving
    #     weeks = (self.end_date - self.start_date).days // 7
    #     self.total_amount = self.calculate_total_amount(weeks)
    #     super().save(*args, **kwargs)


class MessTransaction(models.Model):
    STATUS_CHOICES = [
        ('due', 'Due'),
        ('completed', 'Completed'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("cash-bank", "Cash and Bank"),
    ]


    date = models.DateField(auto_now_add=True)
    received_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    cash_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    bank_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    mess = models.ForeignKey(
        'Mess', related_name='transactions', on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"Transaction on {self.date} - {self.status}"

transaction_creation = False

@receiver(post_save, sender=Mess)
def create_initial_transaction(sender, instance, created, **kwargs):
    global transaction_creation
    if created and not instance.initial_transaction_created:
        transaction_creation = True
        status = 'completed' if instance.pending_amount == 0 else 'due'
        
        try:
            with transaction.atomic():
                # Create the initial Transaction entry
                MessTransaction.objects.create(
                    received_amount=instance.paid_amount,
                    status=status,
                    cash_amount=instance.cash_amount,
                    bank_amount=instance.bank_amount,
                    payment_method=instance.payment_method,
                    mess=instance
                )
                # Set the flag to True
                instance.initial_transaction_created = True
                instance.save()
        except Exception as e:
            print(f"Error creating initial transaction: {e}")
        finally:
            transaction_creation = False


@receiver(post_save, sender=MessTransaction)
def update_mess_on_transaction_save(sender, instance, **kwargs):
    if transaction_creation:
        return  # Skip updating Mess if a transaction is being created

    mess = instance.mess
    if mess:
        try:
            with transaction.atomic():
                # Update Mess fields based on the Transaction
                mess.pending_amount -= instance.received_amount
                mess.paid_amount += instance.received_amount
                mess.cash_amount += instance.cash_amount
                mess.bank_amount += instance.bank_amount
                
                # Ensure Mess is saved only if changes are actually made
                mess.save()
        except Exception as e:
            print(f"Error updating mess on transaction save: {e}")

class CreditUser(models.Model):
    username = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=10, unique=True)
    bill_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(default=default_time_period)
    total_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    limit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("bill_date",)

    def __str__(self):
        return self.username

    def add_to_total_due(self, amount):
        self.total_due += amount
        self.save()

    def make_payment(self, amount):
        if amount > self.total_due:
            amount = self.total_due
        self.total_due -= amount
        self.due_date = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        if self.total_due >= self.limit_amount:
            self.is_active = False
        return super().save(*args, **kwargs)


class CreditOrder(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    credit_user = models.ForeignKey(
        CreditUser, on_delete=models.CASCADE, related_name="credit_orders"
    )

    class Meta:
        ordering = ("credit_user", "order__created_at")

    def __str__(self):
        return f"Credit Order for Order {self.order.id}"
    

class CreditTransaction(models.Model):
    STATUS_CHOICES = [
        ('due', 'Due'),
        ('completed', 'Completed'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("cash-bank", "Cash and Bank"),
    ]


    date = models.DateField(auto_now_add=True)
    received_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    cash_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    bank_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    credit_user = models.ForeignKey(
        'CreditUser', related_name='credittransactions', on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"Transaction on {self.date} - {self.status}"

    def save(self, *args, **kwargs):
        if self.credit_user and self.credit_user.total_due > 0:
            self.status = 'due'
        else:
            self.status = 'completed'

        super().save(*args, **kwargs)

        if self.credit_user:
            self.credit_user.total_due -= self.received_amount
            self.credit_user.save()

@receiver(post_save, sender=CreditUser)
def create_ledger_for_credit_user(sender, instance, created, **kwargs):
    if created:
        try:
            # Find the 'Sundry Debtors' group
            sundry_debtors_group = MainGroup.objects.get(name="Sundry Debtors")
            
            # Create a new Ledger entry
            Ledger.objects.create(
                name=instance.username,
                mobile_no=instance.mobile_number,
                group=sundry_debtors_group,
            )
        except MainGroup.DoesNotExist:
            # Handle the case where the 'Sundry Debtors' group doesn't exist
            print("MainGroup 'Sundry Debtors' does not exist.")


