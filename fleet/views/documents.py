import mimetypes
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import DocumentForm
from ..models import Document, Driver, Vehicle
from ..utils import is_ajax, log_activity, paginate, require_perm, safe_next

EXPIRY_FILTERS = [('expired', 'Expired'), ('30', 'Expiring ≤ 30 days'), ('60', 'Expiring ≤ 60 days'),
                  ('none', 'No expiry date')]


@require_perm('fleet.view_document')
def document_list(request):
    today = timezone.localdate()
    qs = Document.objects.select_related('vehicle', 'driver', 'uploaded_by', 'breakdown')
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(name__icontains=q) | Q(original_filename__icontains=q) | Q(vehicle__registration_no__icontains=q)
                       | Q(driver__name__icontains=q))
    if cat := request.GET.get('category'):
        qs = qs.filter(category=cat)
    if vid := request.GET.get('vehicle'):
        qs = qs.filter(vehicle_id=vid)
    exp = request.GET.get('expiry')
    if exp == 'expired':
        qs = qs.filter(expiry_date__lt=today)
    elif exp in ('30', '60'):
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=int(exp)))
    elif exp == 'none':
        qs = qs.filter(expiry_date__isnull=True)
    return render(request, 'fleet/documents/list.html', {
        'page': paginate(request, qs, 25),
        'categories': Document.Category.choices,
        'vehicles': Vehicle.objects.only('id', 'registration_no'),
        'expiry_filters': EXPIRY_FILTERS,
        'form': DocumentForm(initial={'vehicle': request.GET.get('vehicle')}),
        'has_any': Document.objects.exists(),
        'max_mb': settings.DOCUMENT_MAX_UPLOAD_MB,
        'accept': ','.join(Document.ALLOWED_EXTENSIONS),
        'active_nav': 'documents',
    })


@require_perm('fleet.add_document')
def document_upload(request):
    initial = {k: request.GET[k] for k in ('vehicle', 'driver', 'category') if request.GET.get(k)}
    form = DocumentForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST':
        if form.is_valid():
            doc = form.save(commit=False)
            upload = form.cleaned_data['file']
            doc.name = form.cleaned_data['name']
            doc.original_filename = upload.name[:255]
            doc.content_type = getattr(upload, 'content_type', '') or ''
            doc.size = upload.size
            doc.uploaded_by = request.user
            doc.save()
            target = doc.vehicle or doc.driver
            log_activity(request, 'document_uploaded', f'{doc.get_category_display()} uploaded'
                         + (f' for {target}' if target else '') + f': {doc.name}', doc.vehicle,
                         (doc.vehicle.get_absolute_url() + '?tab=documents') if doc.vehicle else '')
            if is_ajax(request):
                messages.success(request, f'"{doc.name}" uploaded.')
                return JsonResponse({'ok': True, 'redirect': safe_next(request, 'fleet:document_list')})
            messages.success(request, f'"{doc.name}" uploaded.')
            return redirect(safe_next(request, 'fleet:document_list'))
        if is_ajax(request):
            return JsonResponse({'ok': False, 'errors': {k: [str(m) for m in v] for k, v in form.errors.items()}},
                                status=400)
    return render(request, 'fleet/documents/form.html', {'form': form, 'next': request.GET.get('next', ''),
                                                         'active_nav': 'documents'})


@require_perm('fleet.change_document')
def document_edit(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    form = DocumentForm(request.POST or None, request.FILES or None, instance=doc)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        if upload := request.FILES.get('file'):
            doc.original_filename = upload.name[:255]
            doc.content_type = getattr(upload, 'content_type', '') or ''
            doc.size = upload.size
        doc.save()
        messages.success(request, 'Document updated.')
        return redirect(safe_next(request, 'fleet:document_list'))
    return render(request, 'fleet/documents/form.html', {'form': form, 'doc': doc, 'next': request.GET.get('next', ''),
                                                         'active_nav': 'documents'})


@require_POST
@require_perm('fleet.delete_document')
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    log_activity(request, 'document_deleted', f'Document deleted: {doc.name}', doc.vehicle)
    doc.file.delete(save=False)
    doc.delete()
    messages.success(request, 'Document deleted.')
    return redirect(safe_next(request, 'fleet:document_list'))


@require_perm('fleet.view_document')
def document_file(request, pk):
    """The only way to read a stored document: requires login and the view_document permission."""
    doc = get_object_or_404(Document, pk=pk)
    try:
        handle = doc.file.open('rb')
    except FileNotFoundError:
        raise Http404('File missing from storage')
    inline = request.GET.get('inline') == '1' and doc.previewable
    content_type = mimetypes.guess_type(doc.original_filename)[0] or 'application/octet-stream'
    resp = FileResponse(handle, as_attachment=not inline, filename=doc.original_filename, content_type=content_type)
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Cache-Control'] = 'private, no-store'
    if inline:
        resp['X-Frame-Options'] = 'SAMEORIGIN'
        resp['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'self'"
    return resp
