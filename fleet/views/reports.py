from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from .. import finance
from ..models import Breakdown, Expense, Vehicle
from .common import current_records, fleet_qs, tabular_response, with_expiries

REPORTS = [
    ('fleet_register', 'Fleet Register', 'Every vehicle with status, ownership, driver and expiry dates.', 'car', False),
    ('compliance', 'Insurance & Road Tax Status', 'Current cover and road tax for each vehicle, most urgent first.', 'shield', False),
    ('expense_vehicle', 'Expenses by Vehicle', 'Actual spend per vehicle for the selected period.', 'wallet', True),
    ('expense_category', 'Expenses by Category', 'Actual spend per category for the selected period.', 'chart', True),
    ('breakdowns', 'Breakdown & Repair Log', 'Breakdowns reported in the selected period with costs.', 'wrench', True),
]


def _fleet_register():
    headers = ['Registration No.', 'Type', 'Make / Model', 'Year', 'Status', 'Ownership', 'Primary Driver',
               'Department', 'Location', 'Insurance Expiry', 'Road Tax Expiry']
    qs = with_expiries(Vehicle.objects.exclude(status__in=Vehicle.INACTIVE_STATUSES)
                       .select_related('department', 'location').prefetch_related('assignments__driver'))
    rows = [[v.registration_no, v.get_vehicle_type_display(), v.make_model, v.year, v.get_status_display(),
             v.get_ownership_type_display(), str(v.primary_driver or ''), str(v.department or ''),
             str(v.location or ''), v.ins_expiry, v.rt_expiry] for v in qs]
    return headers, rows, None


def _compliance():
    today = timezone.localdate()
    headers = ['Registration No.', 'Document', 'Provider', 'Reference', 'Expiry Date', 'Days Remaining', 'Status']
    current = current_records()
    rows = []
    for v in fleet_qs():
        for kind, label in (('insurance', 'Insurance'), ('road_tax', 'Road Tax')):
            r = current.get((v.pk, kind))
            if r is None and not v.requires(kind):
                continue
            if r is None:
                rows.append([v.registration_no, label, '', '', None, None, 'Not recorded'])
                continue
            days = (r.expiry_date - today).days
            status = 'Expired' if days < 0 else 'Due within 30 days' if days <= 30 else 'Valid'
            rows.append([v.registration_no, label, r.provider, r.reference_no, r.expiry_date, days, status])
    rows.sort(key=lambda r: (r[5] is None, r[5] if r[5] is not None else 0))
    return headers, rows, None


def _expense_vehicle(start, end):
    headers = ['Registration No.', 'Type', 'Maintenance & Repair (RM)', 'Insurance & Road Tax (RM)', 'Fuel (RM)',
               'Other (RM)', 'Total (RM)', 'Transactions']
    qs = (finance.actual().filter(date__range=(start, end)).values('vehicle__registration_no', 'vehicle__vehicle_type')
          .annotate(maint=Sum('amount', filter=Q(category__in=Expense.MAINTENANCE_CATEGORIES)),
                    comp=Sum('amount', filter=Q(category__in=Expense.COMPLIANCE_CATEGORIES)),
                    fuel=Sum('amount', filter=Q(category=Expense.Category.FUEL)),
                    total=Sum('amount'), n=Count('id')).order_by('-total'))
    types = dict(Vehicle.Type.choices)
    rows = []
    for r in qs:
        known = (r['maint'] or 0) + (r['comp'] or 0) + (r['fuel'] or 0)
        rows.append([r['vehicle__registration_no'], types.get(r['vehicle__vehicle_type'], ''), r['maint'] or 0,
                     r['comp'] or 0, r['fuel'] or 0, r['total'] - known, r['total'], r['n']])
    total = sum((r[6] for r in rows), 0)
    return headers, rows, total


def _expense_category(start, end):
    headers = ['Category', 'Total (RM)', 'Share (%)', 'Transactions']
    data = finance.by_category(start, end)
    rows = [[c['label'], c['total'], round(c['share'], 1), c['n']] for c in data]
    return headers, rows, sum((c['total'] for c in data), 0)


def _breakdowns(start, end):
    headers = ['ID', 'Vehicle', 'Reported', 'Problem', 'Severity', 'Workshop', 'Status', 'Estimated (RM)',
               'Final (RM)', 'Days to Repair']
    rows = []
    for b in Breakdown.objects.select_related('vehicle').filter(reported_on__range=(start, end)).order_by('reported_on'):
        days = (b.completed_on - b.reported_on).days if b.completed_on else None
        rows.append([b.code, b.vehicle.registration_no, b.reported_on, b.problem, b.get_severity_display(),
                     b.workshop, b.get_status_display(), b.estimated_cost, b.actual_cost, days])
    return headers, rows, None


@login_required
def reports(request):
    key = request.GET.get('report', '')
    meta = {r[0]: r for r in REPORTS}
    period, start, end, period_label = finance.resolve_period(request.GET)
    if request.GET.get('period') is None and key in ('breakdowns',):
        period, start, end, period_label = 'ytd', end.replace(month=1, day=1), end, 'Year-to-Date'
    result = None
    if key in meta:
        builder = {'fleet_register': _fleet_register, 'compliance': _compliance}.get(key)
        headers, rows, total = builder() if builder else {
            'expense_vehicle': _expense_vehicle, 'expense_category': _expense_category,
            'breakdowns': _breakdowns}[key](start, end)
        if fmt := request.GET.get('export'):
            return tabular_response(key.replace('_', '-'), headers, rows, fmt, meta[key][1])
        money_cols = {i for i, h in enumerate(headers) if '(RM)' in h}
        total_col = headers.index('Total (RM)') if 'Total (RM)' in headers else min(money_cols, default=None)
        result = {'key': key, 'title': meta[key][1], 'desc': meta[key][2], 'uses_period': meta[key][4],
                  'headers': headers, 'rows': rows, 'total': total, 'money_cols': money_cols, 'total_col': total_col,
                  'generated': timezone.localtime()}
    return render(request, 'fleet/reports.html', {
        'reports': REPORTS, 'result': result, 'periods': finance.PERIODS, 'period': period,
        'period_label': period_label, 'period_start': start, 'period_end': end,
        'active_nav': 'reports',
    })
