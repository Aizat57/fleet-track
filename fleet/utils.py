from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Activity


def require_perm(*perms):
    """login_required + every listed model permission, else 403."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perms(perms):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def log_activity(request, verb, message, vehicle=None, url=''):
    Activity.objects.create(actor=request.user if request.user.is_authenticated else None,
                            verb=verb, message=message[:255], vehicle=vehicle, url=url)


def paginate(request, qs, per_page=25):
    page = Paginator(qs, per_page).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    page.querystring = params.urlencode()
    return page


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def safe_next(request, default):
    """POSTed/GET `next` URL if it points back into this site, else `default` (URL name or path)."""
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return resolve_url(default)
