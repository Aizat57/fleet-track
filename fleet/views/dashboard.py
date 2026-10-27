from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .. import finance
from ..alerts import compute_alerts
from ..models import Activity, ComplianceRecord, Expense, Vehicle
from .common import current_records, fleet_qs

STATUS_COLORS = {
    # Status palette: reserved meaning, always paired with a text label in the legend.
    Vehicle.Status.ACTIVE: '#16A34A',
    Vehicle.Status.AVAILABLE: '#2563EB',
    Vehicle.Status.MAINTENANCE: '#D97706',
    Vehicle.Status.OUT_OF_SERVICE: '#DC2626',
}


def greeting(now):
    h = now.hour
    if h < 12:
        return 'Good morning'
    if h < 18:
        return 'Good afternoon'
    return 'Good evening'


def compliance_counts(today=None):
    today = today or timezone.localdate()
    current = current_records()
    counts = {'ins_expired': 0, 'rt_expired': 0, 'within_30': 0, 'within_60': 0}
    for (_vid, kind), r in current.items():
        days = (r.expiry_date - today).days
        if days < 0:
            counts['ins_expired' if kind == ComplianceRecord.Kind.INSURANCE else 'rt_expired'] += 1
        else:
            if days <= 30:
                counts['within_30'] += 1
            if days <= 60:
                counts['within_60'] += 1
    return counts


def status_distribution():
    rows = dict(fleet_qs().values_list('status').annotate(n=Count('id')))
    base = reverse('fleet:vehicle_list')
    dist = []
    for value, label in Vehicle.Status.choices:
        if value in Vehicle.INACTIVE_STATUSES:
            continue
        dist.append({'key': value, 'label': label, 'value': rows.get(value, 0), 'color': STATUS_COLORS[value],
                     'url': f'{base}?status={value}'})
    return dist


@login_required
def dashboard(request):
    now = timezone.localtime()
    today = now.date()
    fleet = fleet_qs()
    counts = fleet.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status=Vehicle.Status.ACTIVE)),
        available=Count('id', filter=Q(status=Vehicle.Status.AVAILABLE)),
        maintenance=Count('id', filter=Q(status=Vehicle.Status.MAINTENANCE)),
        out_of_service=Count('id', filter=Q(status=Vehicle.Status.OUT_OF_SERVICE)),
    )
    period, start, end, period_label = finance.resolve_period(request.GET, today)
    alerts = compute_alerts(request.user)
    has_expenses = Expense.objects.exists()
    trend = finance.monthly_series(12, today=today)
    context = {
        'greeting': greeting(now),
        'today': today,
        'counts': counts,
        'compliance': compliance_counts(today),
        'has_vehicles': counts['total'] > 0 or Vehicle.objects.exists(),
        'finance': finance.summary(start, end) if has_expenses else None,
        'has_expenses': has_expenses,
        'periods': finance.PERIODS,
        'period': period,
        'period_start': start,
        'period_end': end,
        'period_label': period_label,
        'trend': trend,
        'distribution': status_distribution(),
        'attention': alerts[:8],
        'attention_total': len(alerts),
        'activities': Activity.objects.select_related('actor', 'vehicle')[:8],
        'expiry_60': today + timedelta(days=60),
        'active_nav': 'dashboard',
    }
    return render(request, 'fleet/dashboard.html', context)
