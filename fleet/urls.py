from django.urls import path

from .views import compliance, dashboard, documents, drivers, expenses, maintenance, misc, reports, vehicles

app_name = 'fleet'

urlpatterns = [
    path('', dashboard.dashboard, name='dashboard'),

    path('vehicles/', vehicles.vehicle_list, name='vehicle_list'),
    path('vehicles/new/', vehicles.vehicle_create, name='vehicle_create'),
    path('vehicles/import/', vehicles.vehicle_import, name='vehicle_import'),
    path('vehicles/drafts/<int:pk>/delete/', vehicles.draft_delete, name='draft_delete'),
    path('vehicles/<int:pk>/', vehicles.vehicle_detail, name='vehicle_detail'),
    path('vehicles/<int:pk>/edit/', vehicles.vehicle_edit, name='vehicle_edit'),
    path('vehicles/<int:pk>/photo/', vehicles.vehicle_photo, name='vehicle_photo'),
    path('vehicles/<int:pk>/assign/', vehicles.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/end/', vehicles.assignment_end, name='assignment_end'),

    path('drivers/', drivers.driver_list, name='driver_list'),
    path('drivers/new/', drivers.driver_create, name='driver_create'),
    path('drivers/<int:pk>/', drivers.driver_detail, name='driver_detail'),
    path('drivers/<int:pk>/edit/', drivers.driver_edit, name='driver_edit'),
    path('drivers/<int:pk>/assign/', drivers.driver_assign, name='driver_assign'),

    path('renewals/', compliance.compliance, name='compliance'),
    path('vehicles/<int:vehicle_pk>/<str:kind>/new/', compliance.compliance_renew, name='compliance_renew'),
    path('renewals/<int:pk>/edit/', compliance.compliance_edit, name='compliance_edit'),
    path('renewals/<int:pk>/workflow/', compliance.compliance_workflow, name='compliance_workflow'),

    path('maintenance/', maintenance.maintenance, name='maintenance'),
    path('maintenance/breakdowns/new/', maintenance.breakdown_create, name='breakdown_create'),
    path('maintenance/breakdowns/<int:pk>/', maintenance.breakdown_detail, name='breakdown_detail'),
    path('maintenance/breakdowns/<int:pk>/edit/', maintenance.breakdown_edit, name='breakdown_edit'),
    path('maintenance/breakdowns/<int:pk>/progress/', maintenance.breakdown_progress, name='breakdown_progress'),
    path('maintenance/breakdowns/<int:pk>/upload/', maintenance.breakdown_upload, name='breakdown_upload'),
    path('maintenance/tasks/new/', maintenance.task_create, name='task_create'),
    path('maintenance/tasks/<int:pk>/done/', maintenance.task_complete, name='task_complete'),

    path('expenses/', expenses.expense_list, name='expense_list'),
    path('expenses/new/', expenses.expense_create, name='expense_create'),
    path('expenses/<int:pk>/edit/', expenses.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', expenses.expense_delete, name='expense_delete'),

    path('documents/', documents.document_list, name='document_list'),
    path('documents/upload/', documents.document_upload, name='document_upload'),
    path('documents/<int:pk>/edit/', documents.document_edit, name='document_edit'),
    path('documents/<int:pk>/delete/', documents.document_delete, name='document_delete'),
    path('documents/<int:pk>/file/', documents.document_file, name='document_file'),

    path('reports/', reports.reports, name='reports'),
    path('notifications/', misc.notifications, name='notifications'),
    path('notifications/read/', misc.notifications_read, name='notifications_read'),
    path('settings/', misc.settings_view, name='settings'),
    path('settings/<str:kind>/add/', misc.master_add, name='master_add'),
    path('settings/<str:kind>/<int:pk>/delete/', misc.master_delete, name='master_delete'),
    path('search/', misc.search, name='search'),
]
