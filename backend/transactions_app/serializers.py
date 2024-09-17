from rest_framework import serializers
from .models import (
    NatureGroup,
    MainGroup,
    Ledger,
    SharePaymentHistory, 
    Transaction,
    IncomeStatement,
    BalanceSheet,
    ShareUsers,
    ShareUserTransaction,
    ProfitLossShareTransaction,
    CashCountSheet,
    CashCountSheetItems

    )

class NatureGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = NatureGroup
        fields = '__all__'

class MainGroupSerializer(serializers.ModelSerializer):
    nature_group = NatureGroupSerializer(read_only=True)  
    class Meta:
        model = MainGroup
        fields = '__all__'

class LedgerSerializer(serializers.ModelSerializer):
    group = MainGroupSerializer(read_only=True)  
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=MainGroup.objects.all(), write_only=True, source='group'
    )

    class Meta:
        model = Ledger
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    ledger_id = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all(), source='ledger', write_only=True)
    ledger = LedgerSerializer(read_only=True)
    particulars_id = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all(), source='particulars', write_only=True)
    particulars =  LedgerSerializer(read_only=True)
    class Meta:
        model = Transaction
        fields = '__all__'



class IncomeStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeStatement
        fields = '__all__'

class BalanceSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSheet
        fields = '__all__'

#ShareManagement
class ShareUserManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareUsers
        fields = ['id', 'name', 'mobile_no', 'category', 'profitlose_share', 'address']

def get_next_transaction_no():
    # Get the last transaction and increment the number
    last_transaction = ProfitLossShareTransaction.objects.order_by('-created_date').first()
    if last_transaction:
        last_transaction_no = last_transaction.transaction_no
        next_transaction_no = str(int(last_transaction_no) + 1)
    else:
        # If there are no transactions yet, start with 1
        next_transaction_no = '1'
    return next_transaction_no

class ShareUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareUsers
        fields = ['id', 'name', 'category']

class ShareUserTransactionSerializer(serializers.ModelSerializer):
    share_user = serializers.PrimaryKeyRelatedField(queryset=ShareUsers.objects.all()) 
    share_user_data = ShareUserSerializer(source='share_user', read_only=True)
    class Meta:
        model = ShareUserTransaction
        fields = ['share_user', 'share_user_data','profit_lose', 'percentage', 'amount','percentage_amount','balance_amount']

class ProfitLossShareTransactionSerializer(serializers.ModelSerializer):
    share_user_transactions = ShareUserTransactionSerializer(many=True)

    class Meta:
        model = ProfitLossShareTransaction
        fields = [
            'transaction_no',
            'created_date',
            'period_from',
            'period_to',
            'status',
            'profit_amount',
            'loss_amount',
            'total_amount',
            'total_percentage',
            'share_user_transactions'
        ]
        read_only_fields = ('transaction_no',)  # Make transaction_no read-only

    def create(self, validated_data):
        # Generate the next transaction number
        transaction_no = get_next_transaction_no()
        validated_data['transaction_no'] = transaction_no
        
        share_users_data = validated_data.pop('share_user_transactions')
        transaction = ProfitLossShareTransaction.objects.create(**validated_data)
        
        # Calculate total_amount and total_percentage
        total_amount = sum(user_data['amount'] for user_data in share_users_data)
        total_percentage = sum(user_data['percentage'] for user_data in share_users_data)
        
        transaction.total_amount = total_amount
        transaction.total_percentage = total_percentage
        transaction.save()

        for share_user_data in share_users_data:
            ShareUserTransaction.objects.create(transaction=transaction, **share_user_data)
        
        return transaction

class ShareUserTransactionViewSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareUserTransaction
        fields = ['transaction', 'share_user', 'percentage', 'profit_lose', 'amount', 'percentage_amount']

class CashCountSheetItemsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashCountSheetItems
        fields = ['id', 'created_date', 'currency', 'nos', 'amount']

class CashCountSheetSerializer(serializers.ModelSerializer):
    # Nested serializer for items related to the cash sheet
    items = CashCountSheetItemsSerializer(many=True)

    class Meta:
        model = CashCountSheet
        fields = ['id', 'created_date', 'voucher_number', 'amount', 'transaction_type', 'items']

    def create(self, validated_data):
        # Pop out the items data from the validated data
        items_data = validated_data.pop('items')
        
        # Create the CashCountSheet instance
        cash_sheet = CashCountSheet.objects.create(**validated_data)
        
        # Create the related CashCountSheetItems instances
        for item_data in items_data:
            CashCountSheetItems.objects.create(ref=cash_sheet, **item_data)
        
        return cash_sheet

    def update(self, instance, validated_data):
        # Update CashCountSheet fields
        instance.voucher_number = validated_data.get('voucher_number', instance.voucher_number)
        instance.amount = validated_data.get('amount', instance.amount)
        instance.transaction_type = validated_data.get('transaction_type', instance.transaction_type)
        instance.save()

        # Update or create items
        items_data = validated_data.pop('items', [])
        for item_data in items_data:
            item_instance = CashCountSheetItems.objects.filter(ref=instance, currency=item_data['currency']).first()
            if item_instance:
                # Update the existing item
                item_instance.nos = item_data.get('nos', item_instance.nos)
                item_instance.amount = item_data.get('amount', item_instance.amount)
                item_instance.save()
            else:
                # Create new item if not exists
                CashCountSheetItems.objects.create(ref=instance, **item_data)
        
        return instance


#individual Transaction
class ProfitLossShareTransactionIndividualListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfitLossShareTransaction
        fields = ['transaction_no', 'created_date', 'period_from', 'period_to', 'total_percentage', 'total_amount', 'status', 'profit_amount', 'loss_amount']


class ShareUserTransactionIndividualListSerializer(serializers.ModelSerializer):
    transaction = ProfitLossShareTransactionIndividualListSerializer(read_only=True)
    share_user_data = serializers.StringRelatedField(source='share_user', read_only=True)

    class Meta:
        model = ShareUserTransaction
        fields = ['id','share_user_data', 'transaction', 'percentage', 'profit_lose', 'amount', 'percentage_amount','balance_amount']

class SharePaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SharePaymentHistory
        fields = '__all__'