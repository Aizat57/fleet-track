from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (Activity, Assignment, Breakdown, BreakdownUpdate, ComplianceRecord, Department, Document, Driver,
                     Expense, Location, ServiceTask, Vehicle)

admin.site.register([Department, Location])


@admin.register(Vehicle)
class VehicleAdmin(SimpleHistoryAdmin):
    list_display = ['registration_no', 'vehicle_type', 'make', 'model', 'status', 'department']
    list_filter = ['vehicle_type', 'status', 'ownership_type', 'department']
    search_fields = ['registration_no', 'make', 'model', 'chassis_no']


@admin.register(Driver)
class DriverAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'staff_no', 'phone', 'status', 'licence_expiry']
    search_fields = ['name', 'staff_no', 'licence_no']


@admin.register(ComplianceRecord)
class ComplianceAdmin(SimpleHistoryAdmin):
    list_display = ['vehicle', 'kind', 'provider', 'expiry_date', 'cost', 'workflow']
    list_filter = ['kind', 'workflow']
    search_fields = ['vehicle__registration_no', 'reference_no']


class UpdateInline(admin.TabularInline):
    model = BreakdownUpdate
    extra = 0


@admin.register(Breakdown)
class BreakdownAdmin(SimpleHistoryAdmin):
    list_display = ['code', 'vehicle', 'reported_on', 'problem', 'severity', 'status']
    list_filter = ['severity', 'status']
    inlines = [UpdateInline]


@admin.register(Expense)
class ExpenseAdmin(SimpleHistoryAdmin):
    list_display = ['date', 'vehicle', 'category', 'amount', 'payment_status']
    list_filter = ['category', 'payment_status']
    search_fields = ['vehicle__registration_no', 'description', 'supplier']


@admin.register(Document)
class DocumentAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'category', 'vehicle', 'expiry_date', 'uploaded_by', 'uploaded_at']
    list_filter = ['category']
    exclude = ['file']


admin.site.register([Assignment, ServiceTask], SimpleHistoryAdmin)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'verb', 'message']
    list_filter = ['verb']
    readonly_fields = [f.name for f in Activity._meta.fields]

    def has_add_permission(self, request):
        return False
