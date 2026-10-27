from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..alerts import compute_alerts
from ..forms import DepartmentForm, LocationForm, ProfileForm
from ..models import Activity, Breakdown, Department, Document, Driver, Location, NotificationRead, Vehicle
from ..utils import paginate, require_perm, safe_next

PRIORITY_FILTERS = [('', 'All'), ('critical', 'Critical'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]


@login_required
def notifications(request):
    alerts = compute_alerts(request.user)
    priority = request.GET.get('priority', '')
    if request.GET.get('unread'):
        alerts = [a for a in alerts if not a.read]
    shown = [a for a in alerts if not priority or a.priority == priority]
    return render(request, 'fleet/notifications.html', {
        'alerts': shown, 'priority': priority, 'priority_filters': PRIORITY_FILTERS,
        'counts': {p: sum(1 for a in alerts if a.priority == p) for p, _ in PRIORITY_FILTERS if p},
        'activities': paginate(request, Activity.objects.select_related('actor', 'vehicle'), 20),
        'active_nav': 'notifications',
    })


@require_POST
@login_required
def notifications_read(request):
    keys = request.POST.getlist('key')
    if request.POST.get('all'):
        keys = [a.key for a in compute_alerts(request.user) if not a.read]
    for key in keys[:500]:
        NotificationRead.objects.get_or_create(user=request.user, key=key[:80])
    return redirect(safe_next(request, 'fleet:notifications'))


@login_required
def settings_view(request):
    profile = ProfileForm(request.POST or None, instance=request.user, prefix='profile')
    if request.method == 'POST' and request.POST.get('section') == 'profile' and profile.is_valid():
        profile.save()
        messages.success(request, 'Profile updated.')
        return redirect('fleet:settings')
    return render(request, 'fleet/settings.html', {
        'profile': profile,
        'departments': Department.objects.all(),
        'locations': Location.objects.all(),
        'dept_form': DepartmentForm(prefix='dept'),
        'loc_form': LocationForm(prefix='loc'),
        'groups': request.user.groups.all(),
        'active_nav': 'settings',
    })


@require_POST
@require_perm('fleet.add_department', 'fleet.add_location')
def master_add(request, kind):
    form_cls, prefix = (DepartmentForm, 'dept') if kind == 'department' else (LocationForm, 'loc')
    form = form_cls(request.POST, prefix=prefix)
    if form.is_valid():
        form.save()
        messages.success(request, f'{form.cleaned_data["name"]} added.')
    else:
        messages.error(request, ' '.join(m for errs in form.errors.values() for m in errs))
    return redirect('fleet:settings')


@require_POST
@require_perm('fleet.delete_department', 'fleet.delete_location')
def master_delete(request, kind, pk):
    model = Department if kind == 'department' else Location
    obj = get_object_or_404(model, pk=pk)
    try:
        obj.delete()
        messages.success(request, f'{obj.name} removed. Vehicles and drivers that used it are now unassigned.')
    except IntegrityError:
        messages.error(request, f'{obj.name} is in use and cannot be removed.')
    return redirect('fleet:settings')


@login_required
def search(request):
    q = request.GET.get('q', '').strip()
    results = {}
    if len(q) >= 2:
        results = {
            'vehicles': Vehicle.objects.filter(Q(registration_no__icontains=q) | Q(make__icontains=q)
                                               | Q(model__icontains=q) | Q(chassis_no__icontains=q))[:10],
            'drivers': Driver.objects.filter(Q(name__icontains=q) | Q(staff_no__icontains=q) | Q(phone__icontains=q))[:10],
            'breakdowns': Breakdown.objects.select_related('vehicle').filter(
                Q(problem__icontains=q) | Q(vehicle__registration_no__icontains=q) | Q(workshop__icontains=q))[:10],
        }
        if request.user.has_perm('fleet.view_document'):
            results['documents'] = Document.objects.select_related('vehicle').filter(
                Q(name__icontains=q) | Q(original_filename__icontains=q))[:10]
        if q.upper().startswith('BD-') and q[3:].isdigit():
            results['breakdowns'] = Breakdown.objects.select_related('vehicle').filter(pk=int(q[3:]))
        exact = Vehicle.objects.filter(registration_no__iexact=' '.join(q.upper().split())).first()
        if exact and request.GET.get('go'):
            return redirect(exact)
    return render(request, 'fleet/search.html', {
        'q': q, 'results': results, 'total': sum(len(v) for v in results.values()),
    })
