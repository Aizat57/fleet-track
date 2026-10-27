import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from simple_history.models import HistoricalRecords

# Documents live outside MEDIA_ROOT so they can only be downloaded through a permission-checked view.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def document_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'documents/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}'


def vehicle_image_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'vehicles/{uuid.uuid4().hex}{ext}'


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    class Type(models.TextChoices):
        CAR = 'car', 'Car'
        SUV = 'suv', 'SUV / 4x4'
        MPV = 'mpv', 'MPV'
        PICKUP = 'pickup', 'Pickup Truck'
        VAN = 'van', 'Van'
        BUS = 'bus', 'Bus'
        MOTORCYCLE = 'motorcycle', 'Motorcycle'
        BICYCLE = 'bicycle', 'Bicycle'
        TRUCK = 'truck', 'Truck / Lorry'
        TANKER = 'tanker', 'Tanker'
        PRIME_MOVER = 'prime_mover', 'Trailer Head / Prime Mover'
        TRAILER = 'trailer', 'Trailer'
        FORKLIFT = 'forklift', 'Forklift'
        EXCAVATOR = 'excavator', 'Excavator / Backhoe'
        CRANE = 'crane', 'Crane'
        TRACTOR = 'tractor', 'Tractor'
        BOAT = 'boat', 'Boat / Vessel'
        JET_SKI = 'jet_ski', 'Jet Ski'
        HELICOPTER = 'helicopter', 'Helicopter'
        AIRCRAFT = 'aircraft', 'Aircraft'
        DRONE = 'drone', 'Drone'
        OTHER = 'other', 'Other'

    TYPE_GROUPS = [
        ('Road vehicles', [Type.CAR, Type.SUV, Type.MPV, Type.PICKUP, Type.VAN, Type.BUS, Type.MOTORCYCLE,
                           Type.BICYCLE]),
        ('Commercial & haulage', [Type.TRUCK, Type.TANKER, Type.PRIME_MOVER, Type.TRAILER]),
        ('Heavy equipment', [Type.FORKLIFT, Type.EXCAVATOR, Type.CRANE, Type.TRACTOR]),
        ('Marine', [Type.BOAT, Type.JET_SKI]),
        ('Aviation', [Type.HELICOPTER, Type.AIRCRAFT, Type.DRONE]),
        ('Other', [Type.OTHER]),
    ]
    # JPJ road tax (LKM) only applies to registered road vehicles; everything else is not flagged when missing.
    ROAD_TAX_TYPES = (Type.CAR, Type.SUV, Type.MPV, Type.PICKUP, Type.VAN, Type.BUS, Type.MOTORCYCLE, Type.TRUCK,
                      Type.TANKER, Type.PRIME_MOVER, Type.TRAILER)
    INSURANCE_EXEMPT_TYPES = (Type.BICYCLE,)
    NO_DRIVER_TYPES = (Type.TRAILER,)
    NO_ENGINE_TYPES = (Type.TRAILER, Type.BICYCLE)
    ODOMETER_TYPES = (Type.CAR, Type.SUV, Type.MPV, Type.PICKUP, Type.VAN, Type.BUS, Type.MOTORCYCLE, Type.TRUCK,
                      Type.TANKER, Type.PRIME_MOVER)
    ENGINE_HOURS_TYPES = (Type.FORKLIFT, Type.EXCAVATOR, Type.CRANE, Type.TRACTOR, Type.BOAT, Type.JET_SKI,
                          Type.HELICOPTER, Type.AIRCRAFT, Type.DRONE)

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        AVAILABLE = 'available', 'Available'
        MAINTENANCE = 'maintenance', 'Under Maintenance'
        OUT_OF_SERVICE = 'out_of_service', 'Out of Service'
        ARCHIVED = 'archived', 'Archived'
        SOLD = 'sold', 'Sold'
        DISPOSED = 'disposed', 'Disposed'

    # Statuses that are no longer part of the operating fleet.
    INACTIVE_STATUSES = (Status.ARCHIVED, Status.SOLD, Status.DISPOSED)

    class Ownership(models.TextChoices):
        OWNED = 'owned', 'Company Owned'
        FINANCED = 'financed', 'Hire Purchase / Financed'
        LEASED = 'leased', 'Leased'
        RENTED = 'rented', 'Rented'

    class Fuel(models.TextChoices):
        PETROL = 'petrol', 'Petrol'
        DIESEL = 'diesel', 'Diesel'
        HYBRID = 'hybrid', 'Hybrid'
        ELECTRIC = 'electric', 'Electric'
        NGV = 'ngv', 'NGV'

    registration_no = models.CharField('registration number', max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=Type.choices)
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    colour = models.CharField(max_length=40, blank=True)
    chassis_no = models.CharField('chassis number', max_length=40, blank=True)
    engine_no = models.CharField('engine number', max_length=40, blank=True)
    image = models.ImageField(upload_to=vehicle_image_upload_to, blank=True)

    ownership_type = models.CharField(max_length=20, choices=Ownership.choices, default=Ownership.OWNED)
    registered_owner = models.CharField(max_length=120, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    financier = models.CharField('financier / lessor', max_length=120, blank=True)
    contract_end = models.DateField('finance / lease end date', null=True, blank=True)
    monthly_instalment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='vehicles')
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='vehicles')
    fuel_type = models.CharField(max_length=20, choices=Fuel.choices, blank=True)
    odometer_km = models.PositiveIntegerField('odometer (km)', null=True, blank=True)
    engine_hours = models.PositiveIntegerField('engine / flight hours', null=True, blank=True)
    seating_capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    gross_weight_kg = models.PositiveIntegerField('gross vehicle weight (kg)', null=True, blank=True)
    permit_no = models.CharField('operating permit / licence no.', max_length=40, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['registration_no']

    def __str__(self):
        return self.registration_no

    def save(self, *args, **kwargs):
        self.registration_no = ' '.join(self.registration_no.upper().split())
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('fleet:vehicle_detail', args=[self.pk])

    @property
    def make_model(self):
        return f'{self.make} {self.model}'.strip()

    @property
    def is_in_fleet(self):
        return self.status not in self.INACTIVE_STATUSES

    @property
    def is_motorised(self):
        return self.vehicle_type not in self.NO_ENGINE_TYPES

    @property
    def takes_driver(self):
        return self.vehicle_type not in self.NO_DRIVER_TYPES

    @property
    def requires_road_tax(self):
        return self.vehicle_type in self.ROAD_TAX_TYPES

    @property
    def requires_insurance(self):
        return self.vehicle_type not in self.INSURANCE_EXEMPT_TYPES

    def requires(self, kind):
        return self.requires_insurance if kind == ComplianceRecord.Kind.INSURANCE else self.requires_road_tax

    def current_record(self, kind):
        """The compliance record with the latest expiry date for this kind, or None."""
        records = [r for r in self.compliance_records.all() if r.kind == kind]
        return max(records, key=lambda r: r.expiry_date, default=None)

    @cached_property
    def current_insurance(self):
        return self.current_record(ComplianceRecord.Kind.INSURANCE)

    @cached_property
    def current_road_tax(self):
        return self.current_record(ComplianceRecord.Kind.ROAD_TAX)

    @cached_property
    def active_assignments(self):
        return [a for a in self.assignments.all() if a.end_date is None]

    @property
    def primary_driver(self):
        active = sorted(self.active_assignments, key=lambda a: not a.is_primary)
        return active[0].driver if active else None


class Driver(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on_leave', 'On Leave'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=120)
    staff_no = models.CharField('staff number', max_length=30, blank=True)
    ic_no = models.CharField('IC number', max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    licence_no = models.CharField('licence number', max_length=40, blank=True)
    licence_classes = models.CharField('licence classes', max_length=60, blank=True, help_text='e.g. D, E, GDL')
    licence_expiry = models.DateField(null=True, blank=True)
    gdl_expiry = models.DateField('GDL / PSV expiry', null=True, blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='drivers')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('fleet:driver_detail', args=[self.pk])

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p[:1].isalpha()]
        return ''.join(p[0] for p in parts[:2]).upper() or '?'


class Assignment(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='assignments')
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='assignments')
    is_primary = models.BooleanField('primary driver', default=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-end_date', '-start_date']

    def __str__(self):
        return f'{self.driver} → {self.vehicle}'


class ComplianceRecord(models.Model):
    """One insurance policy or road tax (LKM) period for a vehicle. Renewals add a new record."""

    class Kind(models.TextChoices):
        INSURANCE = 'insurance', 'Insurance'
        ROAD_TAX = 'road_tax', 'Road Tax'

    class Workflow(models.TextChoices):
        NONE = '', 'Not started'
        PENDING = 'pending', 'Renewal pending'
        IN_PROGRESS = 'in_progress', 'Renewal in progress'

    kind = models.CharField(max_length=20, choices=Kind.choices)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='compliance_records')
    provider = models.CharField('insurer / issuer', max_length=120, blank=True)
    reference_no = models.CharField('policy / reference no.', max_length=60, blank=True)
    coverage = models.CharField(max_length=60, blank=True, help_text='e.g. Comprehensive, Third Party')
    sum_insured = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Leave blank if unknown.')
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+', verbose_name='responsible person')
    workflow = models.CharField('renewal workflow', max_length=20, choices=Workflow.choices, blank=True, default='')
    is_renewal = models.BooleanField(default=False, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-expiry_date']

    def __str__(self):
        return f'{self.get_kind_display()} {self.vehicle} (exp. {self.expiry_date:%d %b %Y})'

    @property
    def days_remaining(self):
        return (self.expiry_date - timezone.localdate()).days

    @property
    def state(self):
        """expired / due_7 / due_30 / valid, computed from the actual expiry date."""
        days = self.days_remaining
        if days < 0:
            return 'expired'
        if days <= 7:
            return 'due_7'
        if days <= settings.FLEET_EXPIRY_WARNING_DAYS:
            return 'due_30'
        return 'valid'


class Breakdown(models.Model):
    class Severity(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        REPORTED = 'reported', 'Reported'
        DIAGNOSING = 'diagnosing', 'Diagnosing'
        AWAITING_APPROVAL = 'awaiting_approval', 'Awaiting Approval'
        AWAITING_PARTS = 'awaiting_parts', 'Awaiting Parts'
        IN_REPAIR = 'in_repair', 'In Repair'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    CLOSED_STATUSES = (Status.COMPLETED, Status.CANCELLED)
    SEVERITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='breakdowns')
    reported_on = models.DateField(default=timezone.localdate)
    location = models.CharField('breakdown location', max_length=160, blank=True)
    problem = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    workshop = models.CharField(max_length=120, blank=True)
    diagnosis = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED)
    completed_on = models.DateField(null=True, blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-reported_on', '-id']

    def __str__(self):
        return f'{self.code} {self.problem}'

    def get_absolute_url(self):
        return reverse('fleet:breakdown_detail', args=[self.pk])

    @property
    def code(self):
        return f'BD-{self.pk:05d}' if self.pk else 'BD-new'

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES


class BreakdownUpdate(models.Model):
    breakdown = models.ForeignKey(Breakdown, on_delete=models.CASCADE, related_name='updates')
    status = models.CharField(max_length=20, choices=Breakdown.Status.choices)
    note = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at', 'id']


class ServiceTask(models.Model):
    """Planned maintenance, e.g. 10,000 km service, PUSPAKOM inspection, tyre change."""

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='service_tasks')
    title = models.CharField(max_length=120)
    due_date = models.DateField()
    due_odometer_km = models.PositiveIntegerField('due at odometer (km)', null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    workshop = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['completed_on', 'due_date']

    def __str__(self):
        return f'{self.title} – {self.vehicle}'

    @property
    def is_overdue(self):
        return self.completed_on is None and self.due_date < timezone.localdate()


class Expense(models.Model):
    class Category(models.TextChoices):
        FUEL = 'fuel', 'Fuel'
        MAINTENANCE = 'maintenance', 'Maintenance'
        REPAIR = 'repair', 'Repair'
        TYRES = 'tyres', 'Tyres'
        INSURANCE = 'insurance', 'Insurance'
        ROAD_TAX = 'road_tax', 'Road Tax'
        TOLL_PARKING = 'toll_parking', 'Toll & Parking'
        PERMIT = 'permit', 'Permits & Inspection'
        FINANCING = 'financing', 'Instalment / Lease'
        FINE = 'fine', 'Summons & Fines'
        OTHER = 'other', 'Other'

    class Payment(models.TextChoices):
        PAID = 'paid', 'Paid'
        OUTSTANDING = 'outstanding', 'Outstanding'
        FORECAST = 'forecast', 'Forecast'

    # Actual spend = paid + outstanding. Forecasts are plans and never counted as spend.
    ACTUAL = (Payment.PAID, Payment.OUTSTANDING)
    MAINTENANCE_CATEGORIES = (Category.MAINTENANCE, Category.REPAIR, Category.TYRES)
    COMPLIANCE_CATEGORIES = (Category.INSURANCE, Category.ROAD_TAX)

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='expenses')
    date = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=200)
    supplier = models.CharField(max_length=120, blank=True)
    invoice_no = models.CharField(max_length=60, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=Payment.choices, default=Payment.PAID)
    breakdown = models.ForeignKey(Breakdown, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses')
    compliance_record = models.ForeignKey(ComplianceRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.date} {self.get_category_display()} RM{self.amount}'


class Document(models.Model):
    class Category(models.TextChoices):
        REGISTRATION = 'registration', 'Registration Card (Geran)'
        INSURANCE = 'insurance', 'Insurance Cover Note / Policy'
        ROAD_TAX = 'road_tax', 'Road Tax'
        PERMIT = 'permit', 'Operating Permit'
        INSPECTION = 'inspection', 'PUSPAKOM Inspection'
        FINANCE = 'finance', 'Finance / Lease Agreement'
        PHOTO = 'photo', 'Photo'
        QUOTATION = 'quotation', 'Repair Quotation'
        INVOICE = 'invoice', 'Invoice / Receipt'
        LICENCE = 'licence', 'Driving Licence'
        OTHER = 'other', 'Other'

    # A vehicle missing any of these appears under "Needs Your Attention".
    ESSENTIAL_FOR_VEHICLE = (Category.REGISTRATION,)
    ALLOWED_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.heic', '.doc', '.docx', '.xls', '.xlsx')

    name = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=Category.choices)
    file = models.FileField(upload_to=document_upload_to, storage=private_storage)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.CASCADE, related_name='documents')
    driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.CASCADE, related_name='documents')
    breakdown = models.ForeignKey(Breakdown, null=True, blank=True, on_delete=models.SET_NULL, related_name='documents')
    compliance_record = models.ForeignKey(ComplianceRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name='documents')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def extension(self):
        return os.path.splitext(self.original_filename)[1].lower()

    @property
    def previewable(self):
        return self.extension in ('.pdf', '.jpg', '.jpeg', '.png', '.webp')

    @property
    def is_image(self):
        return self.extension in ('.jpg', '.jpeg', '.png', '.webp')


class Activity(models.Model):
    """Human-readable event feed for the dashboard; field-level audit lives in simple_history."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    verb = models.CharField(max_length=40)
    message = models.CharField(max_length=255)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities')
    url = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'activities'

    def __str__(self):
        return self.message


class NotificationRead(models.Model):
    """Notifications are computed from live data; this only remembers which ones a user has read."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    key = models.CharField(max_length=80)
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('user', 'key')]


class VehicleDraft(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicle_drafts')
    data = models.JSONField(default=dict)
    step = models.PositiveSmallIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    @property
    def label(self):
        reg = (self.data.get('registration_no') or [''])[0]
        make = (self.data.get('make') or [''])[0]
        return reg or make or f'Untitled draft #{self.pk}'
