from django import forms as dj_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import finance
from ..forms import BreakdownForm, BreakdownProgressForm, ServiceTaskForm, validate_upload
from ..models import Breakdown, BreakdownUpdate, Document, Expense, ServiceTask, Vehicle
from ..utils import log_activity, safe_next, paginate, require_perm
from .common import fleet_qs, tabular_response
from .vehicles import _save_document


@login_required
def maintenance(request):
    today = timezone.localdate()
    qs = Breakdown.objects.select_related('vehicle')
    state = request.GET.get('state', 'open')
    if state == 'open':
        qs = qs.exclude(status__in=Breakdown.CLOSED_STATUSES)
    elif state == 'closed':
        qs = qs.filter(status__in=Breakdown.CLOSED_STATUSES)
    if sev := request.GET.get('severity'):
        qs = qs.filter(severity=sev)
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(vehicle__registration_no__icontains=q) | Q(problem__icontains=q) | Q(workshop__icontains=q))
    if fmt := request.GET.get('export'):
        headers = ['ID', 'Vehicle', 'Reported', 'Problem', 'Severity', 'Workshop', 'Estimated (RM)', 'Final (RM)',
                   'Status', 'Completed']
        rows = [[b.code, b.vehicle.registration_no, b.reported_on, b.problem, b.get_severity_display(), b.workshop,
                 b.estimated_cost, b.actual_cost, b.get_status_display(), b.completed_on] for b in qs]
        return tabular_response('breakdowns', headers, rows, fmt, 'Breakdowns')

    open_qs = Breakdown.objects.exclude(status__in=Breakdown.CLOSED_STATUSES)
    month_start = today.replace(day=1)
    repair_spend = finance.actual().filter(date__range=(month_start, today),
                                           category__in=Expense.MAINTENANCE_CATEGORIES)
    tasks = ServiceTask.objects.select_related('vehicle').filter(completed_on__isnull=True).order_by('due_date')
    summary = {
        'open': open_qs.count(),
        'critical': open_qs.filter(severity=Breakdown.Severity.CRITICAL).count(),
        'under_repair': fleet_qs().filter(status=Vehicle.Status.MAINTENANCE).count(),
        'overdue': tasks.filter(due_date__lt=today).count(),
        'repair_cost': repair_spend.aggregate(s=Sum('amount'))['s'],
        'repair_cost_known': repair_spend.exists(),
    }
    ordered = sorted(qs[:500], key=lambda b: (not b.is_open, Breakdown.SEVERITY_RANK[b.severity], -b.reported_on.toordinal()))
    return render(request, 'fleet/maintenance/index.html', {
        'page': paginate(request, ordered, 25),
        'summary': summary,
        'state': state,
        'severities': Breakdown.Severity.choices,
        'tasks': tasks,
        'recent_done': ServiceTask.objects.select_related('vehicle').filter(completed_on__isnull=False).order_by('-completed_on')[:5],
        'task_form': ServiceTaskForm(),
        'today': today,
        'has_any': Breakdown.objects.exists(),
        'active_nav': 'maintenance',
    })


@require_perm('fleet.add_breakdown')
def breakdown_create(request):
    initial = {}
    if vid := request.GET.get('vehicle'):
        initial['vehicle'] = vid
    form = BreakdownForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            b = form.save(commit=False)
            b.reported_by = request.user
            b.save()
            BreakdownUpdate.objects.create(breakdown=b, status=b.status, user=request.user,
                                           note=b.description or 'Breakdown reported.')
            for photo in form.cleaned_data.get('photos') or []:
                _save_document(request, photo, Document.Category.PHOTO, b.vehicle, breakdown=b)
            if form.cleaned_data.get('take_off_road') and b.vehicle.status != Vehicle.Status.MAINTENANCE:
                b.vehicle.status = Vehicle.Status.MAINTENANCE
                b.vehicle.save(update_fields=['status', 'updated_at'])
            log_activity(request, 'breakdown_reported',
                         f'{b.get_severity_display()} breakdown reported for {b.vehicle}: {b.problem}', b.vehicle,
                         b.get_absolute_url())
        messages.success(request, f'Breakdown {b.code} reported.')
        return redirect(b)
    return render(request, 'fleet/maintenance/breakdown_form.html', {'form': form, 'active_nav': 'maintenance'})


@require_perm('fleet.change_breakdown')
def breakdown_edit(request, pk):
    b = get_object_or_404(Breakdown, pk=pk)
    form = BreakdownForm(request.POST or None, instance=b)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Breakdown details saved.')
        return redirect(b)
    return render(request, 'fleet/maintenance/breakdown_form.html', {'form': form, 'breakdown': b,
                                                                     'active_nav': 'maintenance'})


@login_required
def breakdown_detail(request, pk):
    b = get_object_or_404(Breakdown.objects.select_related('vehicle', 'reported_by'), pk=pk)
    docs = list(b.documents.select_related('uploaded_by'))
    progress = BreakdownProgressForm(initial={
        'status': b.status, 'diagnosis': b.diagnosis, 'workshop': b.workshop, 'estimated_cost': b.estimated_cost,
        'actual_cost': b.actual_cost})
    return render(request, 'fleet/maintenance/breakdown_detail.html', {
        'b': b,
        'updates': b.updates.select_related('user'),
        'photos': [d for d in docs if d.is_image],
        'files': [d for d in docs if not d.is_image],
        'expenses': b.expenses.all(),
        'progress': progress,
        'doc_categories': [(c, Document.Category(c).label) for c in
                           (Document.Category.QUOTATION, Document.Category.INVOICE, Document.Category.PHOTO,
                            Document.Category.OTHER)],
        'active_nav': 'maintenance',
    })


@require_POST
@require_perm('fleet.change_breakdown')
def breakdown_progress(request, pk):
    b = get_object_or_404(Breakdown.objects.select_related('vehicle'), pk=pk)
    form = BreakdownProgressForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please check the update details.')
        return redirect(b)
    d = form.cleaned_data
    with transaction.atomic():
        status_changed = d['status'] != b.status
        b.status = d['status']
        # The form is pre-filled with current values, so a blank field means the user cleared it.
        for f in ('diagnosis', 'workshop', 'estimated_cost', 'actual_cost'):
            setattr(b, f, d[f])
        if b.status == Breakdown.Status.COMPLETED and not b.completed_on:
            b.completed_on = timezone.localdate()
        elif b.status != Breakdown.Status.COMPLETED:
            b.completed_on = None
        b.save()
        BreakdownUpdate.objects.create(breakdown=b, status=b.status, note=d['note'], user=request.user)
        if b.status == Breakdown.Status.COMPLETED:
            if d['record_expense'] and b.actual_cost and not b.expenses.exists():
                Expense.objects.create(vehicle=b.vehicle, date=b.completed_on, category=Expense.Category.REPAIR,
                                       description=f'{b.code} {b.problem}'[:200], supplier=b.workshop,
                                       amount=b.actual_cost, payment_status=Expense.Payment.OUTSTANDING,
                                       breakdown=b, created_by=request.user)
            if d['return_to_service'] and b.vehicle.status == Vehicle.Status.MAINTENANCE and \
                    not b.vehicle.breakdowns.exclude(pk=b.pk).exclude(status__in=Breakdown.CLOSED_STATUSES).exists():
                b.vehicle.status = Vehicle.Status.ACTIVE
                b.vehicle.save(update_fields=['status', 'updated_at'])
        if status_changed:
            verb = 'repair_completed' if b.status == Breakdown.Status.COMPLETED else 'breakdown_updated'
            msg = (f'Repair completed for {b.vehicle} ({b.code})' if b.status == Breakdown.Status.COMPLETED
                   else f'{b.code} on {b.vehicle} moved to {b.get_status_display()}')
            log_activity(request, verb, msg, b.vehicle, b.get_absolute_url())
    messages.success(request, 'Progress update added.')
    return redirect(b)


@require_POST
@require_perm('fleet.add_document')
def breakdown_upload(request, pk):
    b = get_object_or_404(Breakdown.objects.select_related('vehicle'), pk=pk)
    category = request.POST.get('category') or Document.Category.OTHER
    if category not in Document.Category.values:
        category = Document.Category.OTHER
    saved = 0
    for upload in request.FILES.getlist('files'):
        try:
            validate_upload(upload)
        except dj_forms.ValidationError as e:
            messages.error(request, f'{upload.name}: {" ".join(e.messages)}')
            continue
        _save_document(request, upload, category, b.vehicle, breakdown=b)
        saved += 1
    if saved:
        log_activity(request, 'document_uploaded', f'{saved} file(s) added to {b.code} ({b.vehicle})', b.vehicle,
                     b.get_absolute_url())
        messages.success(request, f'{saved} file(s) uploaded.')
    return redirect(b)


@require_POST
@require_perm('fleet.add_servicetask')
def task_create(request):
    form = ServiceTaskForm(request.POST)
    if form.is_valid():
        t = form.save()
        log_activity(request, 'service_scheduled', f'{t.title} scheduled for {t.vehicle} on {t.due_date:%d %b %Y}',
                     t.vehicle, t.vehicle.get_absolute_url() + '?tab=maintenance')
        messages.success(request, 'Maintenance task scheduled.')
    else:
        messages.error(request, 'Could not schedule: ' + '; '.join(f'{form.fields[k].label}: {" ".join(v)}'
                                                                  for k, v in form.errors.items() if k in form.fields))
    return redirect(safe_next(request, 'fleet:maintenance'))


@require_POST
@require_perm('fleet.change_servicetask')
def task_complete(request, pk):
    t = get_object_or_404(ServiceTask.objects.select_related('vehicle'), pk=pk)
    t.completed_on = timezone.localdate()
    t.save()
    log_activity(request, 'service_completed', f'{t.title} completed for {t.vehicle}', t.vehicle,
                 t.vehicle.get_absolute_url() + '?tab=maintenance')
    messages.success(request, f'"{t.title}" marked as done.')
    return redirect(safe_next(request, 'fleet:maintenance'))
