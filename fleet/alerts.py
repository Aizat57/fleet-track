"""Derives compliance and operational alerts from live records.

Nothing here is stored: every alert is recomputed from actual dates and statuses,
so it can never drift from the data. Each alert has a stable `key` so a user's
read/unread state can be remembered in NotificationRead.
"""

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Breakdown, ComplianceRecord, Document, NotificationRead, ServiceTask, Vehicle

PRIORITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


@dataclass
class Alert:
    key: str
    vehicle: Vehicle
    issue: str
    category: str          # insurance / road_tax / breakdown / maintenance / document
    priority: str          # critical / high / medium / low
    status: str            # badge text
    tone: str              # badge tone: danger / warning / info / neutral
    due_date: date | None
    action_url: str
    action_label: str
    read: bool = False

    @property
    def sort_key(self):
        return (PRIORITY_ORDER[self.priority], self.due_date or date.max, self.vehicle.registration_no)


def _compliance_alerts(vehicles, today):
    warn = settings.FLEET_EXPIRY_WARNING_DAYS
    for v in vehicles:
        for kind, label in ComplianceRecord.Kind.choices:
            record = v.current_record(kind)
            renew_url = reverse('fleet:compliance_renew', args=[v.pk, kind])
            if record is None:
                if not v.requires(kind):
                    continue
                yield Alert(f'{kind}-missing-{v.pk}', v, f'{label} details not recorded', kind, 'medium',
                            'Not recorded', 'neutral', None, renew_url, f'Add {label.lower()}')
                continue
            days = (record.expiry_date - today).days
            in_progress = record.workflow == ComplianceRecord.Workflow.IN_PROGRESS
            if days < 0:
                yield Alert(f'{kind}-expired-{record.pk}', v, f'{label} expired', kind, 'critical',
                            'Renewal in progress' if in_progress else 'Expired',
                            'info' if in_progress else 'danger', record.expiry_date, renew_url, 'Renew')
            elif days <= warn:
                yield Alert(f'{kind}-due-{record.pk}', v,
                            f'{label} expires {"today" if days == 0 else f"in {days} day" + ("s" if days != 1 else "")}',
                            kind, 'high' if days <= 7 else 'medium',
                            'Renewal in progress' if in_progress else 'Due soon',
                            'info' if in_progress else 'warning', record.expiry_date, renew_url, 'Renew')


def _breakdown_alerts(vehicle_ids):
    open_breakdowns = (Breakdown.objects.filter(vehicle_id__in=vehicle_ids,
                                                severity__in=[Breakdown.Severity.CRITICAL, Breakdown.Severity.HIGH])
                       .exclude(status__in=Breakdown.CLOSED_STATUSES).select_related('vehicle'))
    for b in open_breakdowns:
        yield Alert(f'breakdown-{b.pk}', b.vehicle, f'{b.get_severity_display()} breakdown: {b.problem}', 'breakdown',
                    'critical' if b.severity == Breakdown.Severity.CRITICAL else 'high',
                    b.get_status_display(), 'danger' if b.severity == Breakdown.Severity.CRITICAL else 'warning',
                    b.reported_on, b.get_absolute_url(), 'View')


def _maintenance_alerts(vehicle_ids, today):
    overdue = (ServiceTask.objects.filter(vehicle_id__in=vehicle_ids, completed_on__isnull=True, due_date__lt=today)
               .select_related('vehicle'))
    for t in overdue:
        yield Alert(f'service-{t.pk}', t.vehicle, f'Overdue maintenance: {t.title}', 'maintenance', 'high',
                    'Overdue', 'danger', t.due_date, reverse('fleet:maintenance') + '#service', 'View')


def _document_alerts(vehicles):
    for v in vehicles:
        have = {d.category for d in v.documents.all()}
        for cat in Document.ESSENTIAL_FOR_VEHICLE:
            if cat not in have:
                label = Document.Category(cat).label
                yield Alert(f'doc-missing-{cat}-{v.pk}', v, f'Missing document: {label}', 'document', 'low',
                            'Missing', 'neutral', None,
                            reverse('fleet:vehicle_detail', args=[v.pk]) + '?tab=documents', 'Upload')


def fleet_vehicles():
    return (Vehicle.objects.exclude(status__in=Vehicle.INACTIVE_STATUSES)
            .prefetch_related('compliance_records', 'documents'))


def compute_alerts(user=None):
    today = timezone.localdate()
    vehicles = list(fleet_vehicles())
    ids = [v.pk for v in vehicles]
    alerts = [
        *_compliance_alerts(vehicles, today),
        *_breakdown_alerts(ids),
        *_maintenance_alerts(ids, today),
        *_document_alerts(vehicles),
    ]
    alerts.sort(key=lambda a: a.sort_key)
    if user is not None and user.is_authenticated:
        read = set(NotificationRead.objects.filter(user=user).values_list('key', flat=True))
        for a in alerts:
            a.read = a.key in read
    return alerts


def notification_alerts(alerts):
    """Alerts worth interrupting someone for (excludes low-priority housekeeping)."""
    return [a for a in alerts if a.priority != 'low']
