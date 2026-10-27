"""Design-system template helpers: icons, badges, money, form fields. Loaded as a template builtin."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# 24px line icons drawn on a 24 grid with 1.75 stroke (Lucide-style geometry).
ICONS = {
    'dashboard': '<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>',
    'car': '<path d="M5 17H3.5a1 1 0 0 1-1-1v-3.2a2 2 0 0 1 .6-1.4L5 9.5l1.6-3.3A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.8 1.2L19 9.5l1.9 1.9a2 2 0 0 1 .6 1.4V16a1 1 0 0 1-1 1H19"/><path d="M5 9.5h14"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/><path d="M9.5 17h5"/>',
    'van': '<path d="M4 17H2.5V7a2 2 0 0 1 2-2H15l4.5 5H21a1 1 0 0 1 1 1v6h-2"/><path d="M15 5v5h4.5"/><path d="M2.5 10H12"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6"/>',
    'bus': '<rect x="4" y="3" width="16" height="15" rx="2.5"/><path d="M4 11h16"/><path d="M12 3v8"/><path d="M7 18v2.5M17 18v2.5"/><circle cx="8" cy="14.5" r=".6" fill="currentColor"/><circle cx="16" cy="14.5" r=".6" fill="currentColor"/>',
    'truck': '<path d="M14 17V6a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v11h2"/><path d="M14 9h4l3.5 4v4H20"/><path d="M14 17h-4"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
    'prime_mover': '<path d="M3 17V9a2 2 0 0 1 2-2h3V4h4l1 3h2l4 4v6h-1.5"/><path d="M12 7v4h7"/><path d="M3 13h9"/><circle cx="7" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/><path d="M9 17h5.5"/>',
    'trailer': '<rect x="2" y="5" width="16" height="9" rx="1.5"/><path d="M18 11h4"/><path d="M2 14v2h16v-2"/><circle cx="7" cy="18" r="2"/><circle cx="12.5" cy="18" r="2"/>',
    'suv': '<path d="M4.5 17H3a1 1 0 0 1-1-1v-4l2-5a2 2 0 0 1 1.9-1.4h9.6a2 2 0 0 1 1.7 1L20 11h1a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-1.5"/><path d="M3 11h17"/><path d="M11 5.6V11"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6"/>',
    'mpv': '<path d="M4.5 17H2.5V9.5L6 5h11l4 4.5V17h-1.5"/><path d="M2.5 10h18"/><path d="M8.5 5v5M14 5v5"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6"/>',
    'pickup': '<path d="M4.5 17H2v-5h9V7h5l3 4h2a1 1 0 0 1 1 1v5h-1.5"/><path d="M11 12h11"/><path d="M14 7v5"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6"/>',
    'motorcycle': '<circle cx="5" cy="16" r="3"/><circle cx="19" cy="16" r="3"/><path d="M5 16 9 10h6l4 6"/><path d="M15 10l-1.5-4H16"/><path d="M8 10h3"/><path d="M10 13h4"/>',
    'bicycle': '<circle cx="5.5" cy="17" r="3.5"/><circle cx="18.5" cy="17" r="3.5"/><path d="M5.5 17 9 9h6l3.5 8"/><path d="M9 9l3 8 3-8"/><path d="M8 6h3"/><path d="M15 9l-1-3h2"/>',
    'tanker': '<path d="M2 15V9a3 3 0 0 1 3-3h7a3 3 0 0 1 3 3v6"/><path d="M15 9h3l3.5 4v4H20"/><path d="M2 15v2h2.5"/><path d="M15 17h-5.5"/><path d="M6 6v9M11 6v9"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
    'forklift': '<path d="M3 18v-6a1 1 0 0 1 1-1h4l2-5h3v12"/><path d="M8 11h5"/><path d="M17 3v15h5"/><path d="M13 15h4"/><circle cx="6" cy="18" r="2"/><circle cx="12" cy="18" r="2"/>',
    'excavator': '<path d="M2 21h13"/><rect x="2" y="16" width="13" height="3.5" rx="1.75"/><path d="M4 16v-4h7v4"/><path d="M11 12l4-7 5 3"/><path d="M20 8v4l-3 1"/>',
    'crane': '<path d="M6 21V3"/><path d="M2.5 21h7"/><path d="M6 3h15"/><path d="M6 8l5-5"/><path d="M18 3v7"/><rect x="16.5" y="10" width="3" height="3" rx=".5"/>',
    'tractor': '<circle cx="7" cy="16" r="4"/><circle cx="18.5" cy="18" r="2"/><path d="M3 12V5h6l2 6h7a2 2 0 0 1 2 2v3"/><path d="M11 18h5.5"/><path d="M15 11V7"/>',
    'boat': '<path d="M2 21c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0"/><path d="M4.5 18 3 13h18l-2 5"/><path d="M12 13V3l6 6h-6"/>',
    'jet_ski': '<path d="M2 21c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0"/><path d="M3 17h15l3-4h-6l-2-3H8l-2 3H3z"/><path d="M12 10l1-4h3"/>',
    'helicopter': '<path d="M3 4h16"/><path d="M11 4v3"/><path d="M5 11a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v1a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z"/><path d="M17 10h5"/><path d="M22 8v4"/><path d="M8 15v3M14 15v3M5 18h12"/>',
    'aircraft': '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    'drone': '<circle cx="5" cy="5" r="2.5"/><circle cx="19" cy="5" r="2.5"/><circle cx="5" cy="19" r="2.5"/><circle cx="19" cy="19" r="2.5"/><rect x="9" y="9" width="6" height="6" rx="1.5"/><path d="M7 7l2 2M17 7l-2 2M7 17l2-2M17 17l-2-2"/>',
    'other': '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    'shield': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    'wrench': '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    'wallet': '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    'file': '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/>',
    'chart': '<path d="M3 3v18h18"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
    'bell': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    'settings': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'upload': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    'import': '<path d="M12 3v12"/><path d="m8 11 4 4 4-4"/><path d="M8 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    'chevron-left': '<path d="m15 18-6-6 6-6"/>',
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'calendar': '<rect x="3" y="4" width="18" height="18" rx="2.5"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    'alert': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
    'alert-circle': '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    'check': '<path d="M20 6 9 17l-5-5"/>',
    'check-circle': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    'clock': '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    'x': '<path d="M18 6 6 18M6 6l12 12"/>',
    'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    'more': '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
    'edit': '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    'trash': '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    'eye': '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    'refresh': '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
    'filter': '<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>',
    'activity': '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    'pause': '<circle cx="12" cy="12" r="10"/><path d="M10 15V9M14 15V9"/>',
    'ban': '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    'receipt': '<path d="M4 2v20l3-2 2 2 3-2 3 2 2-2 3 2V2l-3 2-2-2-3 2-3-2-2 2Z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    'list': '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    'map-pin': '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    'save': '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    'link': '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
}

# Every vehicle type has its own icon named after its value; unknown values fall back to 'other'.

# Status value -> badge tone. Tones map to the semantic palette (never colour alone: badges carry text + dot).
TONES = {
    'active': 'success', 'available': 'info', 'maintenance': 'warning', 'out_of_service': 'danger',
    'archived': 'neutral', 'sold': 'neutral', 'disposed': 'neutral',
    'expired': 'danger', 'due_7': 'warning', 'due_30': 'warning', 'valid': 'success', 'missing': 'neutral',
    'low': 'neutral', 'medium': 'info', 'high': 'warning', 'critical': 'danger',
    'reported': 'danger', 'diagnosing': 'info', 'awaiting_approval': 'info', 'awaiting_parts': 'warning',
    'in_repair': 'warning', 'completed': 'success', 'cancelled': 'neutral',
    'paid': 'success', 'outstanding': 'warning', 'forecast': 'info',
    'on_leave': 'warning', 'inactive': 'neutral',
    'pending': 'info', 'in_progress': 'info',
}


@register.simple_tag
def icon(name, size=18, cls=''):
    body = ICONS.get(name, ICONS['alert-circle'])
    return mark_safe(
        f'<svg class="icon {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>'
    )


@register.simple_tag
def type_icon(vehicle_type, size=18):
    return icon(vehicle_type if vehicle_type in ICONS else 'other', size)


@register.simple_tag
def badge(value, label=None, tone=None):
    tone = tone or TONES.get(str(value), 'neutral')
    return format_html('<span class="badge badge-{}"><span class="badge-dot" aria-hidden="true"></span>{}</span>',
                       tone, label if label is not None else str(value).replace('_', ' ').title())


@register.filter
def tone(value):
    return TONES.get(str(value), 'neutral')


@register.filter
def rm(value, blank='—'):
    """Format as Malaysian Ringgit: RM 12,450.00. None renders as `blank`, never as RM 0.00."""
    if value is None or value == '':
        return blank
    try:
        d = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return blank
    sign = '-' if d < 0 else ''
    return f'{sign}RM {abs(d):,.2f}'


@register.filter
def rm_short(value):
    if value is None:
        return '—'
    v = float(value)
    if abs(v) >= 1_000_000:
        return f'RM {v / 1_000_000:.1f}M'
    if abs(v) >= 10_000:
        return f'RM {v / 1000:.0f}k'
    return rm(value)


@register.filter
def days_until(d):
    if not d:
        return None
    return (d - timezone.localdate()).days


@register.filter
def days_label(days):
    if days is None:
        return '—'
    if days < 0:
        n = -days
        return f'{n} day{"s" if n != 1 else ""} overdue'
    if days == 0:
        return 'Today'
    return f'{days} day{"s" if days != 1 else ""}'


@register.filter
def expiry_state(d):
    if not d:
        return 'missing'
    days = (d - timezone.localdate()).days
    if days < 0:
        return 'expired'
    if days <= 7:
        return 'due_7'
    if days <= 30:
        return 'due_30'
    return 'valid'


EXPIRY_LABEL = {'expired': 'Expired', 'due_7': 'Due ≤ 7 days', 'due_30': 'Due soon', 'valid': 'Valid',
                'missing': 'Not recorded'}


@register.simple_tag
def expiry_badge(d):
    state = expiry_state(d)
    return badge(state, EXPIRY_LABEL[state])


@register.simple_tag
def field(bound_field, wide=False, hint=None):
    """Render a labelled form field with help text, required marker, inline errors and visibility rules."""
    if bound_field is None:
        return ''
    form = bound_field.form
    rule = getattr(form, 'field_rules', {}).get(bound_field.name, {})
    widget = bound_field.field.widget
    if bound_field.errors:
        widget.attrs['aria-invalid'] = 'true'
        widget.attrs['aria-describedby'] = f'{bound_field.auto_id}-error'
    elif bound_field.help_text or hint:
        widget.attrs['aria-describedby'] = f'{bound_field.auto_id}-help'
    return render_to_string('ui/field.html', {
        'f': bound_field, 'wide': wide, 'hint': hint or bound_field.help_text,
        'show_types': ','.join(rule.get('types', [])), 'show_ownership': ','.join(rule.get('ownership', [])),
        'is_checkbox': bound_field.widget_type == 'checkbox',
    })


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Current querystring with some keys replaced (None removes them)."""
    params = context['request'].GET.copy()
    params.pop('page', None)
    for k, v in kwargs.items():
        if v is None or v == '':
            params.pop(k, None)
        else:
            params[k] = v
    encoded = params.urlencode()
    return f'?{encoded}' if encoded else '?'


@register.filter
def initials(user):
    name = (user.get_full_name() or user.username or '?').split()
    return ''.join(p[0] for p in name[:2]).upper()


@register.filter
def display_name(user):
    if not user:
        return 'System'
    return user.get_full_name() or user.username


@register.filter
def get_item(d, key):
    return d.get(key) if hasattr(d, 'get') else None


@register.filter
def filesize(n):
    n = n or 0
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


@register.filter
def is_past(d):
    return isinstance(d, date) and d < timezone.localdate()
