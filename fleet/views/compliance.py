import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import ComplianceForm, WorkflowForm
from ..models import ComplianceRecord, Document, Expense, Vehicle
from ..utils import log_activity, safe_next, require_perm
from .common import current_records, fleet_qs, tabular_response
from .vehicles import _save_document, create_compliance

WINDOWS = [('', 'All'), ('expired', 'Expired'), ('7', '≤ 7 days'), ('30', '≤ 30 days'), ('60', '≤ 60 days'),
           ('missing', 'Not recorded')]


def _rows(params, today):
    """One row per in-fleet vehicle and kind: its current record, or a 'not recorded' placeholder."""
    kind_filter = params.get('kind', '')
    window = params.get('window', '')
    q = params.get('q', '').strip().upper()
    vehicles = fleet_qs()
    current = current_records(vehicles)
    rows = []
    for v in vehicles:
        if q and q not in v.registration_no:
            continue
        for kind, label in ComplianceRecord.Kind.choices:
            if kind_filter and kind != kind_filter:
                continue
            r = current.get((v.pk, kind))
            if r is None and not v.requires(kind):
                continue
            days = (r.expiry_date - today).days if r else None
            if window == 'missing' and r is not None:
                continue
            if window == 'expired' and (days is None or days >= 0):
                continue
            if window in ('7', '30', '60') and (days is None or days < 0 or days > int(window)):
                continue
            if r is None:
                state = 'missing'
            elif days < 0:
                state = 'expired'
            elif r.workflow:
                state = 'in_progress'
            elif days <= 30:
                state = 'due_7' if days <= 7 else 'due_30'
            else:
                state = 'valid'
            rows.append({'vehicle': v, 'kind': kind, 'kind_label': label, 'record': r, 'days': days, 'state': state})
    order = {'expired': 0, 'due_7': 1, 'in_progress': 2, 'due_30': 3, 'missing': 4, 'valid': 5}
    rows.sort(key=lambda x: (order[x['state']], x['days'] if x['days'] is not None else 10**6,
                             x['vehicle'].registration_no))
    return rows


STATE_LABELS = {'expired': 'Expired', 'due_7': 'Due ≤ 7 days', 'due_30': 'Due soon', 'in_progress': 'Renewal in progress',
                'valid': 'Valid', 'missing': 'Not recorded'}
STATE_TONES = {'expired': 'danger', 'due_7': 'warning', 'due_30': 'warning', 'in_progress': 'info', 'valid': 'success',
               'missing': 'neutral'}


def _calendar(rows, month):
    """Weeks (Mon-first) of the month, each day carrying the expiries that fall on it."""
    by_day = {}
    for row in rows:
        r = row['record']
        if r and r.expiry_date.year == month.year and r.expiry_date.month == month.month:
            by_day.setdefault(r.expiry_date.day, []).append(row)
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append([{'date': d, 'in_month': d.month == month.month, 'items': by_day.get(d.day, []) if d.month == month.month else []}
                      for d in week])
    return weeks


@login_required
def compliance(request):
    today = timezone.localdate()
    all_rows = _rows({}, today)
    rows = _rows(request.GET, today)
    for row in rows:
        row['label'] = STATE_LABELS[row['state']]
        row['tone'] = STATE_TONES[row['state']]
    if fmt := request.GET.get('export'):
        headers = ['Registration No.', 'Document', 'Provider', 'Reference', 'Expiry Date', 'Days Remaining', 'Status',
                   'Responsible']
        data = [[r['vehicle'].registration_no, r['kind_label'], r['record'].provider if r['record'] else '',
                 r['record'].reference_no if r['record'] else '', r['record'].expiry_date if r['record'] else None,
                 r['days'], r['label'],
                 (r['record'].responsible.get_full_name() or r['record'].responsible.username)
                 if r['record'] and r['record'].responsible else ''] for r in rows]
        return tabular_response('insurance-road-tax', headers, data, fmt, 'Renewals')

    month_param = request.GET.get('month', '')
    try:
        y, m = (int(x) for x in month_param.split('-'))
        month = date(y, m, 1)
    except ValueError:
        month = today.replace(day=1)
    prev_month = (month - timedelta(days=1)).replace(day=1)
    next_month = (month + timedelta(days=32)).replace(day=1)
    summary = {
        'expired': sum(1 for r in all_rows if r['state'] == 'expired'),
        'due_7': sum(1 for r in all_rows if r['days'] is not None and 0 <= r['days'] <= 7),
        'due_30': sum(1 for r in all_rows if r['days'] is not None and 0 <= r['days'] <= 30),
        'renewed': ComplianceRecord.objects.filter(is_renewal=True, created_at__date__gte=today.replace(day=1)).count(),
    }
    view = request.GET.get('view', 'table')
    return render(request, 'fleet/compliance/index.html', {
        'rows': rows,
        'summary': summary,
        'windows': WINDOWS,
        'view': view,
        'month': month,
        'prev_month': prev_month,
        'next_month': next_month,
        'weeks': _calendar(rows, month) if view == 'calendar' else None,
        'today': today,
        'has_vehicles': fleet_qs().exists(),
        'active_nav': 'compliance',
    })


@require_perm('fleet.add_compliancerecord')
def compliance_renew(request, vehicle_pk, kind):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    if kind not in ComplianceRecord.Kind.values:
        return redirect('fleet:compliance')
    current = vehicle.current_record(kind)
    initial = {'responsible': request.user}
    if current:
        start = current.expiry_date + timedelta(days=1)
        initial.update({'provider': current.provider, 'coverage': current.coverage, 'responsible': current.responsible,
                        'start_date': start, 'expiry_date': start.replace(year=start.year + 1) - timedelta(days=1)})
    elif kind == ComplianceRecord.Kind.ROAD_TAX:
        initial['provider'] = 'JPJ'
    form = ComplianceForm(request.POST or None, request.FILES or None, kind=kind, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        record = create_compliance(request, vehicle, kind, data,
                                   payment_status=data.get('payment_status') or Expense.Payment.PAID,
                                   record_expense=data.get('record_expense'))
        if upload := data.get('document'):
            category = Document.Category.INSURANCE if kind == ComplianceRecord.Kind.INSURANCE else Document.Category.ROAD_TAX
            _save_document(request, upload, category, vehicle, compliance_record=record,
                           name=f'{record.get_kind_display()} {vehicle.registration_no} exp. {record.expiry_date:%d %b %Y}',
                           issue_date=record.start_date, expiry_date=record.expiry_date)
        verb = 'renewed' if record.is_renewal else 'recorded'
        if kind == ComplianceRecord.Kind.ROAD_TAX and record.is_renewal:
            verb = 'updated'
        log_activity(request, f'{kind}_{verb}', f'{record.get_kind_display()} {verb} for {vehicle.registration_no} '
                     f'(expires {record.expiry_date:%d %b %Y})', vehicle, vehicle.get_absolute_url() + f'?tab={kind}')
        messages.success(request, f'{record.get_kind_display()} {verb} for {vehicle.registration_no}.')
        return redirect(safe_next(request, f'{vehicle.get_absolute_url()}?tab={kind}'))
    return render(request, 'fleet/compliance/form.html', {
        'form': form, 'vehicle': vehicle, 'kind': kind, 'kind_label': ComplianceRecord.Kind(kind).label,
        'current': current, 'next': request.GET.get('next', ''), 'active_nav': 'compliance',
    })


@require_perm('fleet.change_compliancerecord')
def compliance_edit(request, pk):
    record = get_object_or_404(ComplianceRecord.objects.select_related('vehicle'), pk=pk)
    form = ComplianceForm(request.POST or None, request.FILES or None, instance=record, kind=record.kind)
    if request.method == 'POST' and form.is_valid():
        record = form.save()
        if upload := form.cleaned_data.get('document'):
            category = Document.Category.INSURANCE if record.kind == ComplianceRecord.Kind.INSURANCE else Document.Category.ROAD_TAX
            _save_document(request, upload, category, record.vehicle, compliance_record=record,
                           issue_date=record.start_date, expiry_date=record.expiry_date)
        log_activity(request, f'{record.kind}_edited', f'{record.get_kind_display()} details edited for {record.vehicle}',
                     record.vehicle, record.vehicle.get_absolute_url() + f'?tab={record.kind}')
        messages.success(request, 'Record updated.')
        return redirect(f'{record.vehicle.get_absolute_url()}?tab={record.kind}')
    return render(request, 'fleet/compliance/form.html', {
        'form': form, 'vehicle': record.vehicle, 'kind': record.kind, 'kind_label': record.get_kind_display(),
        'record': record, 'active_nav': 'compliance',
    })


@require_POST
@require_perm('fleet.change_compliancerecord')
def compliance_workflow(request, pk):
    record = get_object_or_404(ComplianceRecord.objects.select_related('vehicle'), pk=pk)
    form = WorkflowForm(request.POST)
    if form.is_valid():
        record.workflow = form.cleaned_data['workflow']
        if 'responsible' in request.POST:
            record.responsible = form.cleaned_data['responsible']
        record.save()
        label = record.get_workflow_display() if record.workflow else 'Renewal workflow cleared'
        log_activity(request, 'renewal_workflow', f'{record.get_kind_display()} for {record.vehicle}: {label}',
                     record.vehicle, record.vehicle.get_absolute_url() + f'?tab={record.kind}')
        messages.success(request, f'{record.vehicle}: {label.lower()}.')
    return redirect(safe_next(request, 'fleet:compliance'))
