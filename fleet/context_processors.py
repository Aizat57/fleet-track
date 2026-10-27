from django.urls import reverse

from .alerts import compute_alerts, notification_alerts

NAV = [
    ('dashboard', 'Dashboard', 'fleet:dashboard', 'dashboard'),
    ('vehicles', 'Vehicles', 'fleet:vehicle_list', 'car'),
    ('drivers', 'Drivers', 'fleet:driver_list', 'users'),
    ('compliance', 'Insurance & Road Tax', 'fleet:compliance', 'shield'),
    ('maintenance', 'Maintenance & Repairs', 'fleet:maintenance', 'wrench'),
    ('expenses', 'Expenses', 'fleet:expense_list', 'wallet'),
    ('documents', 'Documents', 'fleet:document_list', 'file'),
    ('reports', 'Reports', 'fleet:reports', 'chart'),
    ('notifications', 'Notifications', 'fleet:notifications', 'bell'),
    ('settings', 'Settings', 'fleet:settings', 'settings'),
]


def shell(request):
    """Sidebar items and the header's notification panel for every authenticated page."""
    if not request.user.is_authenticated or not request.resolver_match or \
            request.resolver_match.namespace != 'fleet':
        return {}
    alerts = notification_alerts(compute_alerts(request.user))
    unread = [a for a in alerts if not a.read]
    return {
        'nav_items': [{'key': k, 'label': label, 'url': reverse(name), 'icon': ic} for k, label, name, ic in NAV],
        'header_alerts': alerts[:6],
        'unread_count': len(unread),
        'alert_total': len(alerts),
    }
