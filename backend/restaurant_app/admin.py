from unfold.admin import ModelAdmin as UnflodModelAdmin
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from django.contrib import admin
from django.contrib.auth.models import Group
from restaurant_app.models import *

admin.site.unregister(Group)
admin.site.unregister(BlacklistedToken)
admin.site.unregister(OutstandingToken)

class CustomUserAdmin(UnflodModelAdmin):
    # Define the fields to display in the list view
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')

    # Define which fields are editable and visible
    fieldsets = (
        (None, {'fields': ('username', 'password', 'passcode', 'role')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'gender', 'mobile_number')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # Override the fields to display in the add form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password', 'passcode'),
        }),
    )

    # Define which fields should be readonly
    readonly_fields = ('date_joined', 'last_login')

    # Hide specific fields dynamically
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:  # Hide fields for non-superusers
            fieldsets = (
                (None, {'fields': ('username', 'password')}),
                (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
            )
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            return readonly_fields + ('is_staff', 'is_superuser')
        return readonly_fields


admin.site.register(User, CustomUserAdmin)
admin.site.register(Category, UnflodModelAdmin)
admin.site.register(Dish, UnflodModelAdmin)
admin.site.register(Order, UnflodModelAdmin)
admin.site.register(OrderItem, UnflodModelAdmin)
admin.site.register(Bill, UnflodModelAdmin)
admin.site.register(Notification, UnflodModelAdmin)
admin.site.register(Floor, UnflodModelAdmin)
admin.site.register(Table, UnflodModelAdmin)
admin.site.register(Coupon, UnflodModelAdmin)

@admin.register(Menu)
class MenuAdmin(UnflodModelAdmin):
    list_display = (
        "id",
        "name",
        "day_of_week",
        "sub_total",
        "is_custom",
        "mess_type",
        "created_by",
    )
    list_filter = ("day_of_week", "is_custom", "mess_type", "created_by")
    fields = (
        "name",
        "day_of_week",
        "sub_total",
        "is_custom",
        "mess_type",
        "created_by",
    )
    search_fields = ("name", "day_of_week", "mess_type__name", "created_by")

admin.site.register(MenuItem, UnflodModelAdmin)
admin.site.register(Mess, UnflodModelAdmin)
admin.site.register(MessType, UnflodModelAdmin)

admin.site.register(CreditUser, UnflodModelAdmin)
admin.site.register(CreditOrder, UnflodModelAdmin)
admin.site.register(MessTransaction, UnflodModelAdmin)

admin.site.register(LogoInfo, UnflodModelAdmin)
admin.site.register(DishVariant, UnflodModelAdmin)
admin.site.register(CreditTransaction,UnflodModelAdmin)