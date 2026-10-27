import os

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import (Assignment, Breakdown, BreakdownUpdate, ComplianceRecord, Department, Document, Driver, Expense,
                     Location, ServiceTask, Vehicle)

T = Vehicle.Type
O = Vehicle.Ownership


class StyledFormMixin:
    """Gives every widget the design-system class and turns DateFields into native date pickers."""

    field_rules = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(field, forms.DateField):
                field.widget = w = forms.DateInput(attrs=w.attrs, format='%Y-%m-%d')
                w.input_type = 'date'
            if isinstance(w, (forms.CheckboxInput,)):
                css = 'checkbox'
            elif isinstance(w, forms.Select):
                css = 'select'
            elif isinstance(w, forms.Textarea):
                css = 'textarea'
                w.attrs.setdefault('rows', 3)
            elif isinstance(w, forms.FileInput):
                css = 'file-input'
            else:
                css = 'input'
            w.attrs['class'] = (w.attrs.get('class', '') + ' ' + css).strip()
            if isinstance(field, forms.DecimalField):
                w.attrs.setdefault('inputmode', 'decimal')
                w.attrs.setdefault('step', '0.01')


def validate_upload(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in Document.ALLOWED_EXTENSIONS:
        raise forms.ValidationError(f'"{ext or f.name}" files are not accepted. Allowed: '
                                    + ', '.join(e.lstrip('.').upper() for e in Document.ALLOWED_EXTENSIONS) + '.')
    if f.size > settings.DOCUMENT_MAX_UPLOAD_MB * 1024 * 1024:
        raise forms.ValidationError(f'File is larger than {settings.DOCUMENT_MAX_UPLOAD_MB} MB.')
    return f


# ---------------------------------------------------------------- vehicles

VEHICLE_STEPS = [
    ('basic', 'Basic Information', 'Identify the vehicle.'),
    ('ownership', 'Ownership', 'Who owns it and how it was acquired.'),
    ('compliance', 'Insurance & Road Tax', 'Current cover and road tax. Leave blank if not known yet.'),
    ('driver', 'Driver Assignment', 'Who normally drives this vehicle.'),
    ('operations', 'Operational Information', 'Status, base and specifications.'),
    ('review', 'Documents & Review', 'Attach key documents and check the details.'),
]

VEHICLE_BASIC = ['registration_no', 'vehicle_type', 'make', 'model', 'year', 'colour', 'chassis_no', 'engine_no', 'image']
VEHICLE_OWNERSHIP = ['ownership_type', 'registered_owner', 'purchase_date', 'purchase_price', 'financier', 'contract_end',
                     'monthly_instalment']
VEHICLE_OPERATIONS = ['status', 'department', 'location', 'fuel_type', 'odometer_km', 'engine_hours', 'seating_capacity',
                      'gross_weight_kg', 'permit_no', 'notes']

MOTORISED = [t for t in T.values if t not in Vehicle.NO_ENGINE_TYPES]
PERMIT_TYPES = [T.VAN, T.BUS, T.TRUCK, T.TANKER, T.PRIME_MOVER, T.TRAILER, T.CRANE, T.BOAT, T.HELICOPTER, T.AIRCRAFT,
                T.DRONE]
SEATED = [T.CAR, T.SUV, T.MPV, T.PICKUP, T.VAN, T.BUS, T.BOAT, T.HELICOPTER, T.AIRCRAFT]
LOAD_CARRYING = [T.PICKUP, T.VAN, T.TRUCK, T.TANKER, T.PRIME_MOVER, T.TRAILER]


def grouped_type_choices():
    labels = dict(T.choices)
    return [('', '- Select vehicle type -')] + [(group, [(t, labels[t]) for t in types])
                                                  for group, types in Vehicle.TYPE_GROUPS]


class VehicleForm(StyledFormMixin, forms.ModelForm):
    # Fields that only apply to some vehicle or ownership types. The UI hides them and
    # clean() blanks them, so users are never forced to fill in irrelevant details.
    field_rules = {
        'engine_no': {'types': MOTORISED},
        'fuel_type': {'types': MOTORISED},
        'odometer_km': {'types': list(Vehicle.ODOMETER_TYPES)},
        'engine_hours': {'types': list(Vehicle.ENGINE_HOURS_TYPES)},
        'seating_capacity': {'types': SEATED},
        'gross_weight_kg': {'types': LOAD_CARRYING},
        'permit_no': {'types': PERMIT_TYPES},
        'purchase_date': {'ownership': [O.OWNED, O.FINANCED]},
        'purchase_price': {'ownership': [O.OWNED, O.FINANCED]},
        'financier': {'ownership': [O.FINANCED, O.LEASED, O.RENTED]},
        'contract_end': {'ownership': [O.FINANCED, O.LEASED, O.RENTED]},
        'monthly_instalment': {'ownership': [O.FINANCED, O.LEASED, O.RENTED]},
    }

    class Meta:
        model = Vehicle
        fields = VEHICLE_BASIC + VEHICLE_OWNERSHIP + VEHICLE_OPERATIONS
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}
        labels = {'registration_no': 'Registration / ID number'}
        help_texts = {'registration_no': 'Plate number (e.g. WXY 1234), vessel or aircraft registration (e.g. 9M-ABC), '
                                         'or an asset tag for unregistered items such as bicycles.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle_type'].choices = grouped_type_choices()
        self.fields['registration_no'].widget.attrs.update({'autocomplete': 'off', 'style': 'text-transform:uppercase'})
        self.fields['image'].widget.attrs['accept'] = 'image/*'
        self.fields['year'].widget.attrs.update({'min': 1950, 'max': 2100})

    def clean_registration_no(self):
        reg = ' '.join(self.cleaned_data['registration_no'].upper().split())
        qs = Vehicle.objects.filter(registration_no__iexact=reg)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A vehicle with this registration number already exists.')
        return reg

    def clean(self):
        data = super().clean()
        vtype, ownership = data.get('vehicle_type'), data.get('ownership_type')
        for name, rule in self.field_rules.items():
            if ('types' in rule and vtype and vtype not in rule['types']) or \
               ('ownership' in rule and ownership and ownership not in rule['ownership']):
                data[name] = None if Vehicle._meta.get_field(name).null else ''
        return data


class InitialComplianceForm(StyledFormMixin, forms.Form):
    """Optional insurance / road tax details captured while adding a vehicle."""

    provider = forms.CharField(max_length=120, required=False)
    reference_no = forms.CharField(label='Policy / reference no.', max_length=60, required=False)
    coverage = forms.CharField(max_length=60, required=False)
    start_date = forms.DateField(required=False)
    expiry_date = forms.DateField(required=False)
    cost = forms.DecimalField(label='Cost (RM)', max_digits=10, decimal_places=2, required=False,
                              help_text='Recorded as a paid expense. Leave blank if unknown.')

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        if kind == ComplianceRecord.Kind.ROAD_TAX:
            del self.fields['coverage']
            self.fields['provider'].label = 'Issued by'
            self.fields['provider'].initial = 'JPJ'
        else:
            self.fields['provider'].label = 'Insurer'
            self.fields['coverage'].widget.attrs['placeholder'] = 'Comprehensive / Third Party'

    def has_details(self):
        return any(self.cleaned_data.get(k) not in (None, '') for k in self.fields
                   if not (k == 'provider' and self.cleaned_data.get(k) == 'JPJ'))

    def clean(self):
        data = super().clean()
        if self.has_details() and not data.get('expiry_date'):
            self.add_error('expiry_date', 'Expiry date is required when recording these details.')
        if data.get('start_date') and data.get('expiry_date') and data['start_date'] > data['expiry_date']:
            self.add_error('expiry_date', 'Expiry date must be after the start date.')
        return data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [validate_upload(single(d, initial)) for d in data if d]
        return [validate_upload(single(data, initial))] if data else []


class VehicleSetupForm(StyledFormMixin, forms.Form):
    """Driver assignment and document uploads from the Add Vehicle wizard."""

    driver = forms.ModelChoiceField(queryset=Driver.objects.none(), required=False, empty_label='No driver yet')
    registration_file = forms.FileField(label='Registration card (geran)', required=False, validators=[validate_upload])
    insurance_file = forms.FileField(label='Insurance cover note / policy', required=False, validators=[validate_upload])
    road_tax_file = forms.FileField(label='Road tax', required=False, validators=[validate_upload])
    other_files = MultipleFileField(label='Other documents', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = Driver.objects.exclude(status=Driver.Status.INACTIVE)


# ---------------------------------------------------------------- compliance

class ComplianceForm(StyledFormMixin, forms.ModelForm):
    record_expense = forms.BooleanField(label='Record the cost as an expense', required=False, initial=True)
    payment_status = forms.ChoiceField(choices=[(Expense.Payment.PAID, 'Paid'), (Expense.Payment.OUTSTANDING, 'Outstanding')],
                                       initial=Expense.Payment.PAID, required=False)
    document = forms.FileField(label='Renewed document', required=False, validators=[validate_upload],
                               help_text='Cover note, policy schedule or road tax confirmation.')

    class Meta:
        model = ComplianceRecord
        fields = ['provider', 'reference_no', 'coverage', 'sum_insured', 'start_date', 'expiry_date', 'cost',
                  'responsible', 'workflow']

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        User = get_user_model()
        self.fields['responsible'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['responsible'].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields['cost'].label = 'Cost (RM)'
        self.fields['sum_insured'].label = 'Sum insured (RM)'
        if kind == ComplianceRecord.Kind.ROAD_TAX:
            for f in ('coverage', 'sum_insured'):
                del self.fields[f]
            self.fields['provider'].label = 'Issued by'
        else:
            self.fields['provider'].label = 'Insurer'
        if self.instance.pk:
            for f in ('record_expense', 'payment_status'):
                del self.fields[f]

    def clean(self):
        data = super().clean()
        if data.get('start_date') and data.get('expiry_date') and data['start_date'] > data['expiry_date']:
            self.add_error('expiry_date', 'Expiry date must be after the start date.')
        return data


class WorkflowForm(forms.Form):
    workflow = forms.ChoiceField(choices=ComplianceRecord.Workflow.choices, required=False)
    responsible = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)


# ---------------------------------------------------------------- drivers

class DriverForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Driver
        fields = ['name', 'staff_no', 'ic_no', 'phone', 'email', 'department', 'status', 'licence_no', 'licence_classes',
                  'licence_expiry', 'gdl_expiry', 'notes']


class AssignmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['driver', 'is_primary', 'start_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = Driver.objects.exclude(status=Driver.Status.INACTIVE)


class VehicleAssignmentForm(StyledFormMixin, forms.ModelForm):
    """Assign a vehicle from the driver's side."""

    class Meta:
        model = Assignment
        fields = ['vehicle', 'is_primary', 'start_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.exclude(status__in=Vehicle.INACTIVE_STATUSES).exclude(
            vehicle_type__in=Vehicle.NO_DRIVER_TYPES)


# ---------------------------------------------------------------- maintenance

class BreakdownForm(StyledFormMixin, forms.ModelForm):
    take_off_road = forms.BooleanField(label='Mark vehicle as Under Maintenance', required=False, initial=True)
    photos = MultipleFileField(label='Photos', required=False)

    class Meta:
        model = Breakdown
        fields = ['vehicle', 'reported_on', 'problem', 'severity', 'location', 'description', 'workshop',
                  'estimated_cost']
        labels = {'estimated_cost': 'Estimated cost (RM)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.exclude(status__in=Vehicle.INACTIVE_STATUSES)
        self.fields['photos'].widget.attrs['accept'] = 'image/*'
        self.fields['problem'].widget.attrs['placeholder'] = 'e.g. Engine overheating, flat tyre'
        if self.instance.pk:
            del self.fields['take_off_road']
            del self.fields['photos']


class BreakdownProgressForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(choices=Breakdown.Status.choices)
    note = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False,
                           help_text='Diagnosis, approval, parts ordered, work done…')
    diagnosis = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    workshop = forms.CharField(max_length=120, required=False)
    estimated_cost = forms.DecimalField(label='Estimated cost (RM)', max_digits=10, decimal_places=2, required=False)
    actual_cost = forms.DecimalField(label='Final cost (RM)', max_digits=10, decimal_places=2, required=False)
    record_expense = forms.BooleanField(label='Record final cost as a repair expense', required=False, initial=True)
    return_to_service = forms.BooleanField(label='Return vehicle to Active status', required=False, initial=True)


class ServiceTaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceTask
        fields = ['vehicle', 'title', 'due_date', 'due_odometer_km', 'workshop', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.exclude(status__in=Vehicle.INACTIVE_STATUSES)
        self.fields['title'].widget.attrs['placeholder'] = 'e.g. 10,000 km service, PUSPAKOM inspection'


# ---------------------------------------------------------------- expenses

class ExpenseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['vehicle', 'date', 'category', 'description', 'supplier', 'invoice_no', 'amount', 'payment_status']
        labels = {'amount': 'Amount (RM)'}
        help_texts = {'payment_status': 'Forecast entries are planned costs and are not counted as spend.'}

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


# ---------------------------------------------------------------- documents

class DocumentForm(StyledFormMixin, forms.ModelForm):
    file = forms.FileField(validators=[validate_upload])

    class Meta:
        model = Document
        fields = ['file', 'name', 'category', 'vehicle', 'driver', 'issue_date', 'expiry_date']
        help_texts = {'name': 'Defaults to the file name.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        self.fields['vehicle'].queryset = Vehicle.objects.all()
        if self.instance.pk:
            self.fields['file'].required = False

    def clean(self):
        data = super().clean()
        if not data.get('name') and data.get('file'):
            data['name'] = os.path.splitext(data['file'].name)[0][:160]
        if not data.get('name') and not self.instance.pk:
            self.add_error('name', 'Give the document a name.')
        if data.get('issue_date') and data.get('expiry_date') and data['issue_date'] > data['expiry_date']:
            self.add_error('expiry_date', 'Expiry date must be after the issue date.')
        return data


# ---------------------------------------------------------------- settings / import

class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name']


class LocationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name']


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']


class ImportForm(StyledFormMixin, forms.Form):
    file = forms.FileField(help_text='Excel (.xlsx) or CSV using the template columns.')

    def clean_file(self):
        f = self.cleaned_data['file']
        if os.path.splitext(f.name)[1].lower() not in ('.xlsx', '.csv'):
            raise forms.ValidationError('Upload an .xlsx or .csv file.')
        return f
