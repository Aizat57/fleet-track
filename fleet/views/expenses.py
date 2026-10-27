from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import finance
from ..forms import ExpenseForm
from ..models import Expense, Vehicle
from ..utils import log_activity, paginate, require_perm, safe_next
from .common import tabular_response


@login_required
def expense_list(request):
    period, start, end, period_label = finance.resolve_period(request.GET)
    scope = Expense.objects.all()
    if vid := request.GET.get('vehicle'):
        scope = scope.filter(vehicle_id=vid)
    if cat := request.GET.get('category'):
        scope = scope.filter(category=cat)
    rows = scope.select_related('vehicle').filter(date__range=(start, end))
    if pay := request.GET.get('payment'):
        rows = rows.filter(payment_status=pay)
    if q := request.GET.get('q', '').strip():
        rows = rows.filter(Q(description__icontains=q) | Q(supplier__icontains=q) | Q(invoice_no__icontains=q)
                           | Q(vehicle__registration_no__icontains=q))
    if fmt := request.GET.get('export'):
        headers = ['Date', 'Vehicle', 'Category', 'Description', 'Supplier', 'Invoice No.', 'Amount (RM)', 'Payment Status']
        data = [[e.date, e.vehicle.registration_no, e.get_category_display(), e.description, e.supplier, e.invoice_no,
                 e.amount, e.get_payment_status_display()] for e in rows]
        return tabular_response('expenses', headers, data, fmt, 'Expenses')

    # Forecast entries in the selected range are listed separately so they are never confused with spend.
    return render(request, 'fleet/expenses/list.html', {
        'page': paginate(request, rows, 30),
        'summary': finance.summary(start, end, scope),
        'trend': finance.monthly_series(12, scope),
        'categories': finance.by_category(start, end, scope),
        'periods': finance.PERIODS, 'period': period, 'period_label': period_label,
        'period_start': start, 'period_end': end,
        'category_choices': Expense.Category.choices,
        'payment_choices': Expense.Payment.choices,
        'vehicles': Vehicle.objects.only('id', 'registration_no'),
        'has_any': Expense.objects.exists(),
        'active_nav': 'expenses',
    })


@require_perm('fleet.add_expense')
def expense_create(request):
    initial = {k: request.GET[k] for k in ('vehicle', 'category') if request.GET.get(k)}
    form = ExpenseForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        e = form.save(commit=False)
        e.created_by = request.user
        e.save()
        log_activity(request, 'expense_added', f'{e.get_category_display()} expense of RM {e.amount:,.2f} added for '
                     f'{e.vehicle}', e.vehicle, e.vehicle.get_absolute_url() + '?tab=expenses')
        messages.success(request, 'Expense recorded.')
        if request.POST.get('action') == 'another':
            return redirect(f"{request.path}?vehicle={e.vehicle_id}")
        return redirect(safe_next(request, 'fleet:expense_list'))
    return render(request, 'fleet/expenses/form.html', {'form': form, 'next': request.GET.get('next', ''),
                                                        'active_nav': 'expenses'})


@require_perm('fleet.change_expense')
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Expense updated.')
        return redirect(safe_next(request, 'fleet:expense_list'))
    return render(request, 'fleet/expenses/form.html', {'form': form, 'expense': expense,
                                                        'next': request.GET.get('next', ''), 'active_nav': 'expenses'})


@require_POST
@require_perm('fleet.delete_expense')
def expense_delete(request, pk):
    expense = get_object_or_404(Expense.objects.select_related('vehicle'), pk=pk)
    log_activity(request, 'expense_deleted', f'{expense.get_category_display()} expense of RM {expense.amount:,.2f} '
                 f'deleted for {expense.vehicle}', expense.vehicle)
    expense.delete()
    messages.success(request, 'Expense deleted.')
    return redirect(safe_next(request, 'fleet:expense_list'))
