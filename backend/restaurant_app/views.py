from datetime import timedelta
from decimal import Decimal
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import TokenError, RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, F
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.db.models.functions import TruncDate, TruncHour
from delivery_drivers.models import DeliveryOrder
from delivery_drivers.serializers import DeliveryOrderSerializer
from restaurant_app.models import *
from restaurant_app.serializers import *
from rest_framework.decorators import api_view


User = get_user_model()


class LoginViewSet(viewsets.ModelViewSet, TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = (permissions.AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class PasscodeLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasscodeLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(viewsets.ViewSet):
    permission_classes = (permissions.AllowAny,)

    @action(detail=False, methods=["post"])
    def logout(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out"}, status=status.HTTP_200_OK
            )
        except TokenError as e:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# view set to change the logo info
class LogoInfoViewSet(viewsets.ModelViewSet):
    queryset = LogoInfo.objects.all()
    serializer_class = LogoInfoSerializer

    

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]


class DishViewSet(viewsets.ModelViewSet):
    queryset = Dish.objects.all()
    serializer_class = DishSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["category"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price"]


class DishVariantViewSet(viewsets.ModelViewSet):
    queryset = DishVariant.objects.all()
    serializer_class = DishVariantSerializer

    def get_queryset(self):
        queryset = DishVariant.objects.all()
        dish_id = self.request.query_params.get('dish_id')
        
        if dish_id is not None:
            queryset = queryset.filter(dish_id=dish_id)
        
        return queryset

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        order_type = self.request.query_params.get("order_type", None)
        if order_type:
            queryset = queryset.filter(order_type=order_type)
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel_order(self, request, pk=None):
        order = self.get_object()
        if order.status == 'delivered':
            return Response({"detail": "Delivered orders cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        
        order.status = 'cancelled'
        order.save()
        return Response({"detail": "Order has been cancelled."}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset_by_time_range(self, time_range):
        end_date = timezone.now()
        if time_range == "day":
            start_date = end_date - timedelta(days=1)
        elif time_range == "week":
            start_date = end_date - timedelta(weeks=1)
        elif time_range == "month":
            start_date = end_date - timedelta(days=30)
        elif time_range == "year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)

        return self.queryset.filter(created_at__range=(start_date, end_date))
    
    @action(detail=False, methods=["get"])
    def user_order_history(self, request):
        customer_phone_number = request.query_params.get("customer_phone_number", None)
        
        # Initialize queryset
        queryset = self.get_queryset()
        
        # If customer_phone_number is provided, filter the queryset
        if customer_phone_number:
            queryset = queryset.filter(customer_phone_number=customer_phone_number)
        else:
            # Return an empty queryset if no customer_phone_number is provided
            queryset = queryset.none()
        
        # Serialize and return the response
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])  # Update on 21-08-2024
    def sales_report(self, request):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        order_type = request.query_params.get("order_type")
        payment_method = request.query_params.get("payment_method")
        status = request.query_params.get("order_status")

        from_date = parse_date(from_date) if from_date else None
        to_date = parse_date(to_date) if to_date else None

        queryset = self.get_queryset()

        # Apply date filters if provided
        if from_date and to_date:
            queryset = queryset.filter(
                created_at__date__gte=from_date, created_at__date__lte=to_date
            )
        elif from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        elif to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)

        # Apply additional filters based on query parameters
        if order_type:
            queryset = queryset.filter(order_type=order_type)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if status:
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def dashboard_data(self, request):
        time_range = request.query_params.get("time_range", "month")
        queryset = self.get_queryset_by_time_range(time_range)

        daily_sales = (
            queryset.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(total_sales=Sum("total_amount"), order_count=Count("id"))
            .order_by("date")
        )

        total_income = (
            queryset.aggregate(total_income=Sum("total_amount"))["total_income"] or 0
        )

        popular_time_slots = (
            queryset.annotate(hour=TruncHour("created_at"))
            .values("hour")
            .annotate(order_count=Count("id"))
            .order_by("-order_count")[:5]
        )

        top_dishes = (
            OrderItem.objects.filter(order__in=queryset)
            .values(
                "dish__name",
                "dish__image",
            )
            .annotate(orders=Count("id"))
            .order_by("-orders")[:5]
        )

        category_sales = (
            OrderItem.objects.filter(order__in=queryset)
            .values("dish__category__name")
            .annotate(value=Sum(F("quantity") * F("dish__price")))
            .order_by("-value")
        )

        total_orders = queryset.count()

        avg_order_value = (
            queryset.aggregate(avg_value=Avg("total_amount"))["avg_value"] or 0
        )

        return Response(
            {
                "daily_sales": daily_sales,
                "total_income": total_income,
                "popular_time_slots": popular_time_slots,
                "top_dishes": top_dishes,
                "category_sales": category_sales,
                "total_orders": total_orders,
                "avg_order_value": avg_order_value,
            }
        )

    @action(detail=False, methods=["get"])
    def sales_trends(self, request):
        time_range = request.query_params.get("time_range", "month")
        current_queryset = self.get_queryset_by_time_range(time_range)

        end_date = timezone.now() - timedelta(days=1)
        if time_range == "day":
            start_date = end_date - timedelta(days=1)
            prev_start_date = start_date - timedelta(days=1)
        elif time_range == "week":
            start_date = end_date - timedelta(weeks=1)
            prev_start_date = start_date - timedelta(weeks=1)
        elif time_range == "month":
            start_date = end_date - timedelta(days=30)
            prev_start_date = start_date - timedelta(days=30)
        elif time_range == "year":
            start_date = end_date - timedelta(days=365)
            prev_start_date = start_date - timedelta(days=365)

        prev_queryset = self.queryset.filter(
            created_at__range=(prev_start_date, start_date)
        )

        current_stats = current_queryset.aggregate(
            total_income=Sum("total_amount"),
            total_orders=Count("id"),
            avg_order_value=Avg("total_amount"),
        )

        prev_stats = prev_queryset.aggregate(
            total_income=Sum("total_amount"),
            total_orders=Count("id"),
            avg_order_value=Avg("total_amount"),
        )

        def calculate_trend(current, previous):
            if previous and previous != 0:
                return ((current - previous) / previous) * 100
            return 0

        trends = {
            "total_income_trend": calculate_trend(
                current_stats["total_income"] or 0, prev_stats["total_income"] or 0
            ),
            "total_orders_trend": calculate_trend(
                current_stats["total_orders"] or 0, prev_stats["total_orders"] or 0
            ),
            "avg_order_value_trend": calculate_trend(
                current_stats["avg_order_value"] or 0,
                prev_stats["avg_order_value"] or 0,
            ),
        }

        return Response(trends)


class OrderStatusUpdateViewSet(viewsets.GenericViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderStatusUpdateSerializer

    def partial_update(self, request, pk=None):
        try:
            order = self.get_object()
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            updated_order = serializer.save()

            # Check if the payment method is credit
            if updated_order.payment_method == "credit":
                credit_user_id = updated_order.credit_user_id
                try:
                    credit_user = CreditUser.objects.get(pk=credit_user_id)
                except CreditUser.DoesNotExist:
                    return Response(
                        {"error": "Invalid credit user"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not credit_user.is_active:
                    return Response(
                        {"error": "Credit user account is inactive due to overdue payment"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create the credit order if it doesn't exist
                CreditOrder.objects.get_or_create(order=updated_order, credit_user=credit_user)
                credit_user.add_to_total_due(updated_order.total_amount)

            return Response({"detail": "Order updated successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# view for changing the order type

class OrderTypeChangeViewSet(viewsets.ViewSet):

    @action(detail=True, methods=['put'], url_path='change-type')
    def change_order_type(self, request, pk=None):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderTypeChangeSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            order = serializer.save()

            # Handle the creation or update of DeliveryOrder
            if order.order_type == 'delivery':
                delivery_order, created = DeliveryOrder.objects.get_or_create(order=order)
                delivery_order.driver_id = serializer.validated_data.get('delivery_driver_id')
                delivery_order.status = request.data.get('delivery_order_status', 'pending')
                delivery_order.save()

                # Include the DeliveryOrder details in the response
                delivery_order_serializer = DeliveryOrderSerializer(delivery_order)
                response_data = serializer.data
                response_data['delivery_order'] = delivery_order_serializer.data

                return Response(response_data, status=status.HTTP_200_OK)

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all()
    serializer_class = BillSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')  # Get the status from query params
        if status_param:
            queryset = queryset.filter(order__status=status_param)  # Filter based on order status
        return queryset



class CancelOrderByBillView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, bill_id=None):
        try:
            # Get the bill instance by primary key (bill_id)
            bill = Bill.objects.get(pk=bill_id)
            order = bill.order

            # Check if the order is already canceled
            if order.status == 'cancelled':
                return Response({"detail": "Order is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

            # Change the status of the order to 'cancelled'
            order.status = "cancelled"
            order.save()

            # Ensure the bill remains unaffected by this change
            bill.save()  # This might be redundant, ensure you don’t trigger a new save unintentionally.

            # Return a response indicating the order was cancelled
            return Response({"detail": "Order status updated to cancelled."}, status=status.HTTP_200_OK)

        except Bill.DoesNotExist:
            return Response({"detail": "Bill not found."}, status=status.HTTP_404_NOT_FOUND)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)




class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by("-created_at")
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "notification marked as read"})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        unread_notifications = self.queryset.filter(is_read=False)
        serializer = self.get_serializer(unread_notifications, many=True)
        return Response(serializer.data)


class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.all()
    serializer_class = FloorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        names = [item["name"] for item in serializer.data]
        return Response(names)


class TableViewSet(viewsets.ModelViewSet):
    serializer_class = TableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Table.objects.all()
        floor = self.request.query_params.get("floor")
        if floor:
            queryset = queryset.filter(floor__name=floor)
        return queryset


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessTypeViewSet(viewsets.ModelViewSet):
    queryset = MessType.objects.all()
    serializer_class = MessTypeSerializer


class MenuViewSet(viewsets.ModelViewSet):
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["mess_type", "is_custom", "created_by"]
    search_fields = ["name", "created_by"]

    def get_queryset(self):
        queryset = super().get_queryset()
        mess_type = self.request.query_params.get("mess_type")
        is_custom = self.request.query_params.get("is_custom")
        created_by = self.request.query_params.get("created_by")

        if mess_type:
            try:
                mess_type = int(mess_type)
                queryset = queryset.filter(mess_type=mess_type)
            except ValueError:
                raise ValueError("mess_type should be a number")

        if is_custom is not None:
            is_custom_bool = is_custom.lower() == "true"
            queryset = queryset.filter(is_custom=is_custom_bool)

        if created_by:
            queryset = queryset.filter(created_by=created_by)

        return queryset
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mess = serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        mess = serializer.save()
        return Response(serializer.data)
    

class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer


class MessViewSet(viewsets.ModelViewSet):
    queryset = Mess.objects.all()
    serializer_class = MessSerializer

    def create(self, request, *args, **kwargs):
        # Ensure no `id` is included in the creation data
        data = request.data.copy()
        data.pop("id", None)  # Remove `id` if present

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=False, methods=["get"])
    def mess_report(self, request):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        payment_method = request.query_params.get("payment_method")
        credit = request.query_params.get("credit")
        mess_type_name = request.query_params.get("mess_type")

        # Convert to datetime objects for filtering
        from_date = parse_date(from_date) if from_date else None
        to_date = parse_date(to_date) if to_date else None
        print("from :", from_date, "to :", to_date)

        queryset = self.get_queryset()

        if from_date and to_date:
            queryset = queryset.filter(
                Q(start_date__gte=from_date) & Q(end_date__lte=to_date)
            )
        elif from_date:
            queryset = queryset.filter(start_date__gte=from_date)
        elif to_date:
            queryset = queryset.filter(end_date__lte=to_date)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if credit:
            queryset = queryset.filter(pending_amount__gt=0)
        if mess_type_name:
            try:
                mess_type_instance = MessType.objects.get(name=mess_type_name)
                mess_type_id = mess_type_instance.id
                queryset = queryset.filter(mess_type=mess_type_id)
            except MessType.DoesNotExist:
                return Response({"detail": "Invalid mess_type"}, status=400)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SearchDishesAPIView(APIView):
    def get(self, request):
        query = request.GET.get("search", "")
        if query:
            dishes = Dish.objects.filter(name__icontains=query)
            serializer = DishSerializer(dishes, many=True)
            return Response({"results": serializer.data}, status=status.HTTP_200_OK)
        return Response({"results": []}, status=status.HTTP_200_OK)


class CreditUserViewSet(viewsets.ModelViewSet):
    queryset = CreditUser.objects.all()
    serializer_class = CreditUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def get_active_users(self, request, pk=None):
        active_users = CreditUser.objects.filter(is_active=True)
        serializer = self.get_serializer(active_users, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def make_payment(self, request, pk=None):
        credit_user = self.get_object()
        amount = Decimal(request.data.get("payment_amount", 0))

        if amount <= 0:
            return Response(
                {"error": "Invalid payment amount"}, status=status.HTTP_400_BAD_REQUEST
            )

        credit_user.make_payment(amount)
        return Response(CreditUserSerializer(credit_user).data)


class CreditOrderViewSet(viewsets.ModelViewSet):
    queryset = CreditOrder.objects.all()
    serializer_class = CreditOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

class MessTransactionViewSet(viewsets.ModelViewSet):
    queryset = MessTransaction.objects.all()
    serializer_class = MessTransactionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        mess_id = self.request.query_params.get('mess_id', None)
        if mess_id is not None:
            queryset = queryset.filter(mess_id=mess_id)
        return queryset

class CreditTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = CreditTransactionSerializer
    queryset = CreditTransaction.objects.all()

    
    def get_queryset(self):
        queryset = CreditTransaction.objects.all()
        credit_user_id = self.request.query_params.get('credit_user', None)
        if credit_user_id is not None:
            queryset = queryset.filter(credit_user_id=credit_user_id)
        return queryset
    
    @action(detail=False, methods=['get'])
    def latest_transaction(self, request):
        credit_user_id = request.query_params.get('credit_user', None)
        if not credit_user_id:
            return Response({"error": "credit_user parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the latest transaction based on both date and time
        try:
            latest_transaction = CreditTransaction.objects.filter(credit_user_id=credit_user_id).order_by('-date', '-id').first()
            if not latest_transaction:
                return Response({"error": "No transactions found for the given credit_user"}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = self.get_serializer(latest_transaction)
            return Response(serializer.data)
        except CreditTransaction.DoesNotExist:
            return Response({"error": "No transactions found for the given credit_user"}, status=status.HTTP_404_NOT_FOUND)
