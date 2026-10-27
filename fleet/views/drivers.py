from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import DriverForm, VehicleAssignmentForm
from ..models import Assignment, Department, Driver
from ..utils import log_activity, paginate, require_perm
from .common import tabular_response


@login_required
def driver_list(request):
    qs = Driver.objects.select_related('department').annotate(
        vehicle_count=Count('assignments', filter=Q(assignments__end_date__isnull=True)))
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(name__icontains=q) | Q(staff_no__icontains=q) | Q(phone__icontains=q)
                       | Q(licence_no__icontains=q))
    if s := request.GET.get('status'):
        qs = qs.filter(status=s)
    if d := request.GET.get('department'):
        qs = qs.filter(department_id=d)
    if request.GET.get('licence') == 'expiring':
        qs = qs.filter(licence_expiry__lte=timezone.localdate() + timedelta(days=60))
    if fmt := request.GET.get('export'):
        headers = ['Name', 'Staff No.', 'Phone', 'Email', 'Department', 'Status', 'Licence No.', 'Classes',
                   'Licence Expiry', 'GDL/PSV Expiry', 'Assigned Vehicles']
        rows = [[d.name, d.staff_no, d.phone, d.email, str(d.department or ''), d.get_status_display(), d.licence_no,
                 d.licence_classes, d.licence_expiry, d.gdl_expiry, d.vehicle_count] for d in qs]
        return tabular_response('drivers', headers, rows, fmt, 'Drivers')
    qs = qs.order_by('name').prefetch_related('assignments__vehicle')
    return render(request, 'fleet/drivers/list.html', {
        'page': paginate(request, qs, 25),
        'statuses': Driver.Status.choices,
        'departments': Department.objects.all(),
        'counts': {
            'total': Driver.objects.count(),
            'active': Driver.objects.filter(status=Driver.Status.ACTIVE).count(),
            'unassigned': Driver.objects.filter(status=Driver.Status.ACTIVE).exclude(
                pk__in=Assignment.objects.filter(end_date__isnull=True).values('driver')).count(),
            'licence_expiring': Driver.objects.exclude(status=Driver.Status.INACTIVE).filter(
                licence_expiry__lte=timezone.localdate() + timedelta(days=60)).count(),
        },
        'has_any': Driver.objects.exists(),
        'active_nav': 'drivers',
    })


@require_perm('fleet.add_driver')
def driver_create(request):
    form = DriverForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.save()
        log_activity(request, 'driver_added', f'Driver {d.name} added', url=d.get_absolute_url())
        messages.success(request, f'{d.name} added.')
        return redirect(d)
    return render(request, 'fleet/drivers/form.html', {'form': form, 'active_nav': 'drivers'})


@require_perm('fleet.change_driver')
def driver_edit(request, pk):
    d = get_object_or_404(Driver, pk=pk)
    form = DriverForm(request.POST or None, instance=d)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Driver details saved.')
        return redirect(d)
    return render(request, 'fleet/drivers/form.html', {'form': form, 'driver': d, 'active_nav': 'drivers'})


@login_required
def driver_detail(request, pk):
    d = get_object_or_404(Driver.objects.select_related('department'), pk=pk)
    assignments = d.assignments.select_related('vehicle')
    return render(request, 'fleet/drivers/detail.html', {
        'd': d,
        'current': [a for a in assignments if a.end_date is None],
        'past': [a for a in assignments if a.end_date is not None],
        'documents': d.documents.select_related('uploaded_by'),
        'assign_form': VehicleAssignmentForm(),
        'active_nav': 'drivers',
    })


@require_POST
@require_perm('fleet.add_assignment')
def driver_assign(request, pk):
    d = get_object_or_404(Driver, pk=pk)
    form = VehicleAssignmentForm(request.POST)
    if form.is_valid():
        a = form.save(commit=False)
        a.driver = d
        with transaction.atomic():
            if a.is_primary:
                for old in a.vehicle.assignments.filter(end_date__isnull=True, is_primary=True):
                    old.end_date = a.start_date
                    old.save()
            a.save()
        log_activity(request, 'driver_assigned', f'{d} assigned to {a.vehicle.registration_no}', a.vehicle,
                     a.vehicle.get_absolute_url() + '?tab=drivers')
        messages.success(request, f'{d} assigned to {a.vehicle}.')
    else:
        messages.error(request, 'Choose a vehicle to assign.')
    return redirect(d)
