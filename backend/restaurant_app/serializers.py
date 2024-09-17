from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import update_last_login
from django.contrib.auth import get_user_model
from delivery_drivers.models import DeliveryDriver
from restaurant_app.models import *



User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "role",
            "mobile_number",
            "gender",
            "password",
            "driver_profile",
        ]

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class DriverSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    mobile_number = serializers.CharField(source="user.mobile_number", read_only=True)

    class Meta:
        model = DeliveryDriver
        fields = ["id", "username", "email", "mobile_number", "is_active", "is_available"]


class LoginSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)

        user_data = UserSerializer(self.user).data

        data["user"] = user_data
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data


class PasscodeLoginSerializer(serializers.Serializer):
    passcode = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        passcode = attrs.get("passcode")
        User = get_user_model()

        try:
            user = User.objects.get(passcode=passcode)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid passcode")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        refresh = RefreshToken.for_user(user)
        return {
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

# serializer to change the logo for the company

class LogoInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogoInfo
        fields = '__all__'
        

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class DishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = [
            "id",
            "name",
            "description",
            "price",
            "image",
            "category",
        ]


class DishVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = DishVariant
        fields = ['id', 'name','dish']

class OrderItemSerializer(serializers.ModelSerializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all())

    class Meta:
        model = OrderItem
        fields = ["dish", "quantity","is_newly_added","variants"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    user = UserSerializer(read_only=True)
    delivery_order_status = serializers.CharField(source="delivery_order.status", read_only=True)
    delivery_driver = DriverSerializer(source='delivery_order.driver', read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "created_at",
            "total_amount",
            "status",
            "bill_generated",
            "bank_amount",
            "cash_amount",
            "invoice_number",
            "items",
            "order_type",
            "payment_method",
            "address",
            "customer_name",
            "customer_phone_number",    
            "delivery_charge",
            "delivery_driver_id",
            "delivery_driver",
            "credit_user_id",
            "delivery_order_status",
            "kitchen_note"
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        user = self.context["request"].user
        order = Order.objects.create(user=user, **validated_data)
        total_amount = 0

        for item_data in items_data:
            order_item = OrderItem.objects.create(order=order, **item_data)
            total_amount += order_item.quantity * order_item.dish.price
        
        # Add delivery charge to total amount if it's not the default value
        if order.delivery_charge != 0:
            total_amount += order.delivery_charge

        order.total_amount = total_amount
        order.save()
        return order

    def update(self, instance, validated_data):
        
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Start by resetting the total amount to 0
        total_amount = 0

        # Sum existing items' total amount
        for existing_item in instance.items.all():
            total_amount += existing_item.quantity * existing_item.dish.price

        # Add new items' total amount
        if items_data:
            for item_data in items_data:
                item_data['is_newly_added'] = True  # Marking as newly added
                order_item = OrderItem.objects.create(order=instance, **item_data)
                total_amount += order_item.quantity * order_item.dish.price
        
        # Add delivery charge to total amount if it's not the default value
        if instance.delivery_charge != 0:
            total_amount += instance.delivery_charge

        # Update the total amount
        instance.total_amount = total_amount
        instance.save()
        return instance
    

class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, required=False)
    cash_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    bank_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    credit_user_id = serializers.IntegerField(required=False)

    def validate(self, data):
        status = data.get('status')
        payment_method = data.get('payment_method')

        # If status is "delivered", validate the payment method and related fields
        if status == 'delivered':
            if not payment_method:
                raise serializers.ValidationError("Payment method is required when status is 'delivered'.")

            if payment_method == 'cash':
                data['cash_amount'] = data.get('cash_amount', 0)  # Default to 0 if not provided
                data['bank_amount'] = 0  # Ensure bank_amount is 0 for cash payment method

            if payment_method == 'bank':
                data['bank_amount'] = data.get('bank_amount', 0)  # Default to 0 if not provided
                data['cash_amount'] = 0  # Ensure cash_amount is 0 for bank payment method

            if payment_method == 'cash-bank':
                data['cash_amount'] = data.get('cash_amount', 0)  # Default to 0 if not provided
                data['bank_amount'] = data.get('bank_amount', 0)  # Default to 0 if not provided

            if payment_method == 'credit':
                if 'credit_user_id' not in data:
                    raise serializers.ValidationError("credit_user_id is required for credit payment method.")
                try:
                    credit_user = CreditUser.objects.get(id=data['credit_user_id'])
                    if not credit_user.is_active:
                        raise serializers.ValidationError("Selected credit user is not active.")
                except CreditUser.DoesNotExist:
                    raise serializers.ValidationError("Invalid credit_user_id.")
                data['cash_amount'] = 0  # Ensure cash_amount is 0 for credit payment method
                data['bank_amount'] = 0  # Ensure bank_amount is 0 for credit payment method
        
        return data

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)

        # Only update payment-related fields if the status is "delivered"
        if instance.status == 'delivered':
            instance.payment_method = validated_data.get('payment_method', instance.payment_method)

            if instance.payment_method == 'cash':
                instance.cash_amount = validated_data.get('cash_amount', 0)  # Default to 0 if not provided
                instance.bank_amount = 0  # Reset bank_amount if payment is cash-only

            if instance.payment_method == 'bank':
                instance.bank_amount = validated_data.get('bank_amount', 0)  # Default to 0 if not provided
                instance.cash_amount = 0  # Reset cash_amount if payment is bank-only

            if instance.payment_method == 'cash-bank':
                instance.cash_amount = validated_data.get('cash_amount', 0)  # Default to 0 if not provided
                instance.bank_amount = validated_data.get('bank_amount', 0)  # Default to 0 if not provided

            if instance.payment_method == 'credit':
                instance.credit_user_id = validated_data.get('credit_user_id', instance.credit_user_id)
                instance.cash_amount = 0  # Reset cash_amount if payment is credit
                instance.bank_amount = 0  # Reset bank_amount if payment is credit

        instance.save()
        return instance
    

# serializer for updating the the order type
class OrderTypeChangeSerializer(serializers.ModelSerializer):
    delivery_driver = serializers.CharField(source="delivery_driver.user.username", read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_type', 
            'customer_name', 
            'address', 
            'customer_phone_number', 
            'delivery_charge', 
            'delivery_driver_id',
            'delivery_driver',  
        ]

    def validate(self, data):
        if data['order_type'] == 'delivery':
            if not data.get('customer_name'):
                raise serializers.ValidationError("Customer name is required for delivery orders.")
            if not data.get('address'):
                raise serializers.ValidationError("Delivery address is required for delivery orders.")
            if not data.get('customer_phone_number'):
                raise serializers.ValidationError("Customer phone number is required for delivery orders.")
            if not data.get('delivery_driver_id'):
                raise serializers.ValidationError("A delivery driver must be assigned for delivery orders.")
        return data



    
class BillOrderItemSerializer(serializers.ModelSerializer):
    dish_name = serializers.CharField(source='dish.name', read_only=True)
    item_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['dish_name', 'quantity', 'item_total']

    def get_item_total(self, obj):
        return obj.dish.price * obj.quantity
    

class BillOrderSerializer(serializers.ModelSerializer):
    items = BillOrderItemSerializer(many=True, read_only=True)
    sub_total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'total_amount', 'status', 'bill_generated', 
                  'bank_amount', 'cash_amount', 'invoice_number', 'items', 'order_type', 
                  'payment_method', 'address', 'customer_name', 'customer_phone_number', 
                  'delivery_charge', 'sub_total']

    def get_sub_total(self, obj):
        return sum(item.dish.price * item.quantity for item in obj.items.all())
    

class BillSerializer(serializers.ModelSerializer):
    order = BillOrderSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), write_only=True)

    class Meta:
        model = Bill
        fields = ['id', 'order', 'order_id', 'user', 'total_amount', 'paid', 'billed_at']

    def create(self, validated_data):
        order = validated_data.pop('order_id')
        bill = Bill.objects.create(order=order, user=order.user, **validated_data)
        return bill




class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "user", "message", "created_at", "is_read"]


class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Floor
        fields = ["name"]


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = "__all__"


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_amount",
            "discount_percentage",
            "start_date",
            "end_date",
            "is_active",
            "usage_limit",
            "usage_count",
            "min_purchase_amount",
            "description",
        ]
        read_only_fields = ["usage_count"]


class MessTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessType
        fields = ["id", "name"]


class MenuItemSerializer(serializers.ModelSerializer):
    dish = DishSerializer(read_only=True)
    dish_id = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.all(), write_only=True, source="dish"
    )

    class Meta:
        model = MenuItem
        fields = ["id", "menu", "dish", "dish_id", "meal_type"]


class MenuSerializer(serializers.ModelSerializer):
    menu_items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = [
            "id",
            "name",
            "day_of_week",
            "sub_total",
            "is_custom",
            "mess_type",
            "created_by",
            "menu_items",
        ]


class MessSerializer(serializers.ModelSerializer):
    mess_type = MessTypeSerializer(read_only=True)
    mess_type_id = serializers.PrimaryKeyRelatedField(
        queryset=MessType.objects.all(), write_only=True, source='mess_type'
    )

    class Meta:
        model = Mess
        fields = [
            "id",
            "customer_name",
            "mobile_number",
            "start_date",
            "end_date",
            "mess_type",
            "mess_type_id",
            "payment_method",
            "bank_amount",
            "cash_amount",
            "total_amount",
            "paid_amount",
            "pending_amount",
            "menus",
            "discount_amount",
            "grand_total"
        ]

    def calculate_total_amount(self, menus, weeks):
        weekly_total = sum(menu.sub_total for menu in menus)
        return weekly_total * weeks

    def create(self, validated_data):
        menus_data = validated_data.pop('menus', [])
        mess = Mess.objects.create(**validated_data)
        mess.menus.set(menus_data)

        # Calculate total amount
        weeks = (validated_data['end_date'] - validated_data['start_date']).days // 7
        mess.total_amount = self.calculate_total_amount(mess.menus.all(), weeks)
        mess.save()
        return mess

    def update(self, instance, validated_data):
        menus_data = validated_data.pop('menus', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if menus_data:
            instance.menus.set(menus_data)

        # Calculate total amount
        weeks = (instance.end_date - instance.start_date).days // 7
        instance.total_amount = self.calculate_total_amount(instance.menus.all(), weeks)
        instance.save()
        return instance
    
    

class CreditOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditOrder
        fields = ["id", "order"]


class CreditUserSerializer(serializers.ModelSerializer):
    credit_orders = CreditOrderSerializer(many=True, read_only=True)

    class Meta:
        model = CreditUser
        fields = [
            "id",
            "username",
            "mobile_number",
            "bill_date",
            "due_date",
            "total_due",
            "is_active",
            "credit_orders",
            "limit_amount"
        ]
class MessTransactionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = MessTransaction
        fields = ['id', 'received_amount', 'status', 'cash_amount', 'bank_amount', 'payment_method', 'mess','date']

class CreditTransactionSerializer(serializers.ModelSerializer):
    credit_user_details = serializers.SerializerMethodField()

    class Meta:
        model = CreditTransaction
        fields = '__all__'
        read_only_fields = ['status']
        
    def get_credit_user_details(self, obj):
        if obj.credit_user:
            return CreditUserSerializer(obj.credit_user).data
        return None
