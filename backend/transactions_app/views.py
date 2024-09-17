from rest_framework import viewsets,status
from django.db import transaction 
from django.db.models import Sum, Q
from datetime import datetime

from .models import (
    CashCountSheet,
    NatureGroup,
    MainGroup, 
    Ledger,
    SharePaymentHistory,
    ShareUserTransaction, 
    Transaction,
    IncomeStatement, 
    BalanceSheet,
    ShareUsers
    )
from .serializers import (
     CashCountSheetSerializer,
     NatureGroupSerializer, 
     MainGroupSerializer, 
     LedgerSerializer,
     SharePaymentHistorySerializer,
     ShareUserTransactionIndividualListSerializer,
     ShareUserTransactionSerializer,
     ShareUserTransactionViewSetSerializer, 
     TransactionSerializer,
     IncomeStatementSerializer, 
     BalanceSheetSerializer,
     ShareUserManagementSerializer,
     ProfitLossShareTransaction,
     ProfitLossShareTransactionSerializer
     )
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils.dateparse import parse_date
from rest_framework.exceptions import NotFound

class NatureGroupViewSet(viewsets.ModelViewSet):
    queryset = NatureGroup.objects.all()
    serializer_class = NatureGroupSerializer

class MainGroupViewSet(viewsets.ModelViewSet):
    queryset = MainGroup.objects.all()
    serializer_class = MainGroupSerializer

class LedgerViewSet(viewsets.ModelViewSet):
    queryset = Ledger.objects.all()
    serializer_class = LedgerSerializer

    @action(detail=False, methods=['get'], url_path='filter-by-group')
    def filter_ledger_by_group(self, request):
        group_name = request.query_params.get('group_name')  # Get group name from query params
        
        if group_name:
            # Filter ledgers based on the group name
            ledgers = Ledger.objects.filter(group__name=group_name)
            
            if not ledgers.exists():  # If no ledgers found, return an empty list explicitly
                return Response([])

            # Serialize the filtered ledgers
            serializer = self.get_serializer(ledgers, many=True)
            return Response(serializer.data)
        else:
            return Response({"error": "Group name not provided"}, status=400)
        
    @action(detail=False, methods=['get'], url_path='filter-by-ledger-name')
    def filter_by_ledger_name(self, request):
        ledger_name = request.query_params.get('ledger_name')  

        if ledger_name:
            ledgers = Ledger.objects.filter(name__icontains=ledger_name)
            
            if not ledgers.exists():
                return Response([]) 

            serializer = self.get_serializer(ledgers, many=True)
            return Response(serializer.data)
        else:
            return Response({"error": "Ledger name not provided"}, status=400)

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    # @transaction.atomic
    # def create(self, request, *args, **kwargs):
    #     transaction1_data = request.data.get('transaction1')
    #     transaction2_data = request.data.get('transaction2')

    #     if not transaction1_data or not transaction2_data:
    #         return Response({"error": "Both transaction1 and transaction2 are required."}, status=status.HTTP_400_BAD_REQUEST)

    #     # Generate the next voucher number
    #     last_transaction = Transaction.objects.order_by('-voucher_no').first()
    #     next_voucher_no = (last_transaction.voucher_no + 1) if last_transaction else 1

    #     # Assign the generated voucher number to both transactions
    #     transaction1_data['voucher_no'] = next_voucher_no
    #     transaction2_data['voucher_no'] = next_voucher_no

    #     serializer1 = self.get_serializer(data=transaction1_data)
    #     serializer1.is_valid(raise_exception=True)
    #     self.perform_create(serializer1)

    #     serializer2 = self.get_serializer(data=transaction2_data)
    #     serializer2.is_valid(raise_exception=True)
    #     self.perform_create(serializer2)

    #     return Response(serializer1.data, status=status.HTTP_201_CREATED) 

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        transaction_type = request.data.get('transaction_type', '')
        
        if transaction_type == 'payin' or transaction_type == 'payout':
            return self.handle_pay_in_out(request)
        elif transaction_type == 'salesentry':
            return self.handle_sales_entry(request)
        else:
            return Response({"error": "Invalid transaction type."}, status=status.HTTP_400_BAD_REQUEST)

    def handle_pay_in_out(self, request):
        transaction1 = request.data.get('transaction1')
        transaction2 = request.data.get('transaction2')

        if not transaction1 or not transaction2:
            return Response({"error": "Both transactions are required for Pay In/Out."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the next voucher number
        last_transaction = Transaction.objects.order_by('-voucher_no').first()
        next_voucher_no = (last_transaction.voucher_no + 1) if last_transaction else 1

        created_transactions = []
        for transaction_data in [transaction1, transaction2]:
            transaction_data['voucher_no'] = next_voucher_no
            serializer = self.get_serializer(data=transaction_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            created_transactions.append(serializer.data)

        return Response(created_transactions, status=status.HTTP_201_CREATED)

    def handle_sales_entry(self, request):
        # Define possible transaction keys
        transaction_keys = [
            'salescashtransaction1', 'salescashtransaction2',
            'salesbanktransaction1', 'salesbanktransaction2',
            'purchasetransaction1', 'purchasetransaction2'
        ]
        
        # Filter out the keys that are actually present in the request data
        available_transaction_keys = [key for key in transaction_keys if key in request.data]
        
        if not available_transaction_keys:
            return Response({"error": "At least one transaction is required for Sales Entry."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the next voucher number
        last_transaction = Transaction.objects.order_by('-voucher_no').first()
        next_voucher_no = (last_transaction.voucher_no + 1) if last_transaction else 1

        created_transactions = []
        
        for key in available_transaction_keys:
            transaction_data = request.data[key]
            transaction_data['voucher_no'] = next_voucher_no

            # Convert string amounts to float
            for amount_field in ['debit_amount', 'credit_amount']:
                if amount_field in transaction_data:
                    transaction_data[amount_field] = float(transaction_data[amount_field])

            serializer = self.get_serializer(data=transaction_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            created_transactions.append(serializer.data)

        return Response(created_transactions, status=status.HTTP_201_CREATED)


    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'])
    def ledger_report(self, request):
        ledger_param = request.query_params.get('ledger', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)

        if not ledger_param:
            return Response([])

        # Determine if the parameter is a name or ID
        try:
            ledger_id = int(ledger_param)
            # If it converts to an integer, assume it's an ID
        except ValueError:
            # Otherwise, treat it as a name and fetch the ID
            ledger = Ledger.objects.filter(name=ledger_param).first()
            ledger_id = ledger.id if ledger else None

        if not ledger_id:
            return Response([])

        queryset = self.queryset.filter(ledger__id=ledger_id)

        if from_date:
            from_date = parse_date(from_date)
        if to_date:
            to_date = parse_date(to_date)

        if from_date and to_date:
            queryset = queryset.filter(date__range=(from_date, to_date))
        elif from_date:
            queryset = queryset.filter(date__gte=from_date)
        elif to_date:
            queryset = queryset.filter(date__lte=to_date)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='filter-by-nature-group')
    def filter_by_nature_group(self, request):
        nature_group_name = request.query_params.get('nature_group_name', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)

        # Create a filter condition for nature_group_name
        filters = Q()
        if nature_group_name:
            filters &= Q(ledger__group__nature_group__name__iexact=nature_group_name)

        # Parse and apply the date range filter
        if from_date and to_date:
            from_date_parsed = parse_date(from_date)
            to_date_parsed = parse_date(to_date)

            if from_date_parsed and to_date_parsed:
                filters &= Q(date__range=(from_date_parsed, to_date_parsed))
            else:
                return Response([])  # Return empty response if dates are invalid
        else:
            return Response([])  # Return empty response if both dates are not provided

        # Fetch filtered transactions
        transactions = Transaction.objects.filter(filters)

        # Return empty if no transactions found
        if not transactions.exists():
            return Response([])

        # Serialize and return the filtered data
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='profit-and-loss')
    def profit_and_loss(self, request):
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)

        # Date filters
        filters = Q()
        if from_date and to_date:
            from_date_parsed = parse_date(from_date)
            to_date_parsed = parse_date(to_date)

            if from_date_parsed and to_date_parsed:
                filters &= Q(date__range=(from_date_parsed, to_date_parsed))
            else:
                return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Both from_date and to_date are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Filter transactions for 'Expense' and 'Income'
        expense_transactions = Transaction.objects.filter(
            filters & Q(ledger__group__nature_group__name__iexact='Expense')
        )
        income_transactions = Transaction.objects.filter(
            filters & Q(ledger__group__nature_group__name__iexact='Income')
        )

        # Sum the debit_amount for 'Expense' transactions
        total_expense = expense_transactions.aggregate(total_debit=Sum('debit_amount'))['total_debit'] or 0

        # Sum the credit_amount for 'Income' transactions
        total_income = income_transactions.aggregate(total_credit=Sum('credit_amount'))['total_credit'] or 0

        # Calculate net profit and loss
        net_profit = total_income - total_expense if total_income > total_expense else 0
        net_loss = total_expense - total_income if total_expense > total_income else 0

        return Response({
            'total_expense': total_expense,
            'total_income': total_income,
            'net_profit': net_profit,
            'net_loss': net_loss,
        })




class IncomeStatementViewSet(viewsets.ModelViewSet):
    queryset = IncomeStatement.objects.all()
    serializer_class = IncomeStatementSerializer

class BalanceSheetViewSet(viewsets.ModelViewSet):
    queryset = BalanceSheet.objects.all()
    serializer_class = BalanceSheetSerializer

#ShareManagement Section
class ShareUserManagementViewSet(viewsets.ModelViewSet):
    queryset = ShareUsers.objects.all()
    serializer_class = ShareUserManagementSerializer

    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        # Get the ShareUser
        share_user = self.get_object()

        # Filter the ShareUserTransaction by the selected ShareUser
        transactions = ShareUserTransaction.objects.filter(share_user=share_user).select_related('transaction')

        # Serialize the data
        serializer = ShareUserTransactionIndividualListSerializer(transactions, many=True)
        return Response(serializer.data)

class ProfitLossShareTransactionViewSet(viewsets.ModelViewSet):
    queryset = ProfitLossShareTransaction.objects.all()
    serializer_class = ProfitLossShareTransactionSerializer
    def get_queryset(self):
        queryset = ProfitLossShareTransaction.objects.all()
        transaction_no = self.request.query_params.get('transaction_no', None)
        if transaction_no:
            queryset = queryset.filter(transaction_no=transaction_no)
            if not queryset.exists():
                raise NotFound("Transaction not found")
        return queryset
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

class ShareUserTransactionViewSet(viewsets.ModelViewSet):
    queryset = ShareUserTransaction.objects.all()
    serializer_class = ShareUserTransactionViewSetSerializer

class SharePaymentHistoryViewSet(viewsets.ModelViewSet):
    queryset = SharePaymentHistory.objects.all()
    serializer_class = SharePaymentHistorySerializer

    @action(detail=False, methods=['get'], url_path='by-transaction/(?P<transaction_id>\d+)')
    def by_transaction(self, request, transaction_id=None):
        # Fetch payment histories by transaction ID
        payment_histories = SharePaymentHistory.objects.filter(
            share_user_transaction_id=transaction_id
        )
        serializer = self.get_serializer(payment_histories, many=True)
        return Response(serializer.data)
class CashCountSheetViewSet(viewsets.ModelViewSet):
    queryset = CashCountSheet.objects.all()
    serializer_class = CashCountSheetSerializer