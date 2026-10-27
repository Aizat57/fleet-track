"""Expense aggregation. All figures come from Expense rows; forecasts are never counted as spend."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Expense

PERIODS = [
    ('this_month', 'This Month'),
    ('last_month', 'Last Month'),
    ('last_3', 'Last 3 Months'),
    ('ytd', 'Year-to-Date'),
    ('custom', 'Custom Range'),
]


def month_start(d):
    return d.replace(day=1)


def add_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def resolve_period(params, today=None):
    """Return (key, start, end, label) from request GET params. End date is inclusive."""
    today = today or timezone.localdate()
    key = params.get('period') or 'this_month'
    if key == 'last_month':
        end = month_start(today) - timedelta(days=1)
        start = month_start(end)
    elif key == 'last_3':
        start = add_months(month_start(today), -2)
        end = today
    elif key == 'ytd':
        start = date(today.year, 1, 1)
        end = today
    elif key == 'custom':
        start = parse_date(params.get('start') or '') or month_start(today)
        end = parse_date(params.get('end') or '') or today
        if start > end:
            start, end = end, start
    else:
        key = 'this_month'
        start, end = month_start(today), today
    if key == 'custom':
        label = f'{start:%d %b %Y} – {end:%d %b %Y}'
    else:
        label = dict(PERIODS)[key]
    return key, start, end, label


def actual(qs=None):
    return (qs if qs is not None else Expense.objects.all()).filter(payment_status__in=Expense.ACTUAL)


def summary(start, end, qs=None):
    base = actual(qs).filter(date__range=(start, end))
    agg = base.aggregate(
        total=Sum('amount'),
        maintenance=Sum('amount', filter=Q(category__in=Expense.MAINTENANCE_CATEGORIES)),
        insurance=Sum('amount', filter=Q(category=Expense.Category.INSURANCE)),
        road_tax=Sum('amount', filter=Q(category=Expense.Category.ROAD_TAX)),
        compliance=Sum('amount', filter=Q(category__in=Expense.COMPLIANCE_CATEGORIES)),
        count=Count('id'),
    )
    ytd_start = date(end.year, 1, 1)
    agg['ytd'] = actual(qs).filter(date__range=(ytd_start, end)).aggregate(s=Sum('amount'))['s']
    outstanding = (qs if qs is not None else Expense.objects.all()).filter(payment_status=Expense.Payment.OUTSTANDING)
    agg['outstanding'] = outstanding.aggregate(s=Sum('amount'))['s']
    agg['outstanding_count'] = outstanding.count()
    forecast = (qs if qs is not None else Expense.objects.all()).filter(
        payment_status=Expense.Payment.FORECAST, date__gte=timezone.localdate())
    agg['forecast'] = forecast.aggregate(s=Sum('amount'))['s']
    for k in ('total', 'maintenance', 'insurance', 'road_tax', 'compliance', 'ytd', 'outstanding', 'forecast'):
        agg[k] = agg[k] or Decimal('0')
    return agg


def monthly_series(months=12, qs=None, today=None):
    """Actual spend per month for the last `months` months (oldest first). Empty list if there is no data."""
    today = today or timezone.localdate()
    first = add_months(month_start(today), -(months - 1))
    rows = (actual(qs).filter(date__gte=first, date__lte=today)
            .annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount')))
    by_month = {(r['m'].year, r['m'].month): r['total'] for r in rows}
    if not by_month:
        return []
    series = []
    for i in range(months):
        d = add_months(first, i)
        series.append({'label': d.strftime('%b'), 'full': d.strftime('%B %Y'),
                       'value': float(by_month.get((d.year, d.month), 0))})
    return series


def by_category(start, end, qs=None):
    rows = (actual(qs).filter(date__range=(start, end)).values('category')
            .annotate(total=Sum('amount'), n=Count('id')).order_by('-total'))
    labels = dict(Expense.Category.choices)
    grand = sum((r['total'] for r in rows), Decimal('0'))
    return [{'key': r['category'], 'label': labels.get(r['category'], r['category']), 'total': r['total'], 'n': r['n'],
             'share': float(r['total'] / grand * 100) if grand else 0} for r in rows]
