import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import finance
from .alerts import compute_alerts
from .models import (Assignment, Breakdown, ComplianceRecord, Document, Driver, Expense, Vehicle, VehicleDraft,
                     private_storage)
from .templatetags.ui import rm

TODAY = timezone.localdate()


def make_vehicle(reg='WXY 1234', **kw):
    defaults = dict(vehicle_type='car', make='Proton', model='X70')
    defaults.update(kw)
    return Vehicle.objects.create(registration_no=reg, **defaults)


def record(vehicle, kind='insurance', days=100, **kw):
    return ComplianceRecord.objects.create(vehicle=vehicle, kind=kind, expiry_date=TODAY + timedelta(days=days), **kw)


class TempMediaMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.mkdtemp()
        cls._old_location = private_storage.location
        private_storage._location = cls._media
        private_storage.__dict__.pop('base_location', None)
        private_storage.__dict__.pop('location', None)
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        private_storage._location = cls._old_location
        private_storage.__dict__.pop('base_location', None)
        private_storage.__dict__.pop('location', None)
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()


class AlertTests(TestCase):
    def test_expired_insurance_is_critical_and_first(self):
        v = make_vehicle()
        record(v, 'insurance', -3)
        record(v, 'road_tax', 20)
        alerts = compute_alerts()
        self.assertEqual(alerts[0].issue, 'Insurance expired')
        self.assertEqual(alerts[0].priority, 'critical')
        due = [a for a in alerts if a.category == 'road_tax'][0]
        self.assertEqual(due.priority, 'medium')
        self.assertIn('20 days', due.issue)

    def test_uses_latest_record_after_renewal(self):
        v = make_vehicle()
        record(v, 'insurance', -30)
        record(v, 'insurance', 335)
        record(v, 'road_tax', 200)
        self.assertFalse([a for a in compute_alerts() if a.category == 'insurance' and a.priority != 'low'])

    def test_missing_records_and_documents_flagged(self):
        make_vehicle()
        issues = {a.issue for a in compute_alerts()}
        self.assertIn('Insurance details not recorded', issues)
        self.assertIn('Road Tax details not recorded', issues)
        self.assertIn('Missing document: Registration Card (Geran)', issues)

    def test_road_tax_not_flagged_for_non_road_types(self):
        boat = make_vehicle('9M-BOAT', vehicle_type='boat')
        make_vehicle('BIKE-01', vehicle_type='bicycle')
        record(boat, 'insurance', -2)
        issues = {(a.vehicle.registration_no, a.issue) for a in compute_alerts() if a.category != 'document'}
        self.assertEqual(issues, {('9M-BOAT', 'Insurance expired')})

    def test_sold_vehicles_are_ignored(self):
        v = make_vehicle(status=Vehicle.Status.SOLD)
        record(v, 'insurance', -10)
        self.assertEqual(compute_alerts(), [])

    def test_critical_breakdown_and_overdue_service(self):
        v = make_vehicle()
        Breakdown.objects.create(vehicle=v, problem='Engine fire', severity='critical')
        Breakdown.objects.create(vehicle=v, problem='Done', severity='critical', status='completed')
        v.service_tasks.create(title='Service', due_date=TODAY - timedelta(days=1))
        issues = [a.issue for a in compute_alerts()]
        self.assertIn('Critical breakdown: Engine fire', issues)
        self.assertNotIn('Critical breakdown: Done', issues)
        self.assertIn('Overdue maintenance: Service', issues)


class FinanceTests(TestCase):
    def test_forecast_excluded_and_outstanding_counted(self):
        v = make_vehicle()
        Expense.objects.create(vehicle=v, category='fuel', description='a', amount=Decimal('100'), date=TODAY)
        Expense.objects.create(vehicle=v, category='repair', description='b', amount=Decimal('50'), date=TODAY,
                               payment_status='outstanding')
        Expense.objects.create(vehicle=v, category='tyres', description='c', amount=Decimal('999'), date=TODAY,
                               payment_status='forecast')
        s = finance.summary(TODAY.replace(day=1), TODAY)
        self.assertEqual(s['total'], Decimal('150'))
        self.assertEqual(s['maintenance'], Decimal('50'))
        self.assertEqual(s['outstanding'], Decimal('50'))
        self.assertEqual(s['forecast'], Decimal('999'))

    def test_monthly_series_empty_without_data(self):
        self.assertEqual(finance.monthly_series(), [])

    def test_last_month_period(self):
        key, start, end, _ = finance.resolve_period({'period': 'last_month'}, today=TODAY.replace(month=3, day=15))
        self.assertEqual((start.month, start.day, end.month), (2, 1, 2))

    def test_rm_formatting(self):
        self.assertEqual(rm(Decimal('12450')), 'RM 12,450.00')
        self.assertEqual(rm(None), '—')


class PermissionTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user('viewer', password='x')
        self.viewer.groups.add(Group.objects.get(name='Fleet Viewer'))
        self.manager = User.objects.create_user('manager', password='x')
        self.manager.groups.add(Group.objects.get(name='Fleet Manager'))
        self.vehicle = make_vehicle()
        self.doc = Document.objects.create(name='Geran', category='registration', vehicle=self.vehicle,
                                           file=SimpleUploadedFile('g.pdf', b'%PDF-1.4 test'),
                                           original_filename='g.pdf')

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse('fleet:dashboard'))
        self.assertRedirects(resp, reverse('login') + '?next=/')

    def test_viewer_reads_but_cannot_write(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('fleet:vehicle_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('fleet:vehicle_create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('fleet:expense_create'), {}).status_code, 403)

    def test_viewer_cannot_open_documents(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('fleet:document_file', args=[self.doc.pk])).status_code, 403)

    def test_manager_downloads_and_previews(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('fleet:document_file', args=[self.doc.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp['Content-Disposition'])
        resp = self.client.get(reverse('fleet:document_file', args=[self.doc.pk]) + '?inline=1')
        self.assertIn('inline', resp['Content-Disposition'])

    def test_rejects_disallowed_extension(self):
        self.client.force_login(self.manager)
        resp = self.client.post(reverse('fleet:document_upload'),
                                {'file': SimpleUploadedFile('x.exe', b'MZ'), 'name': 'x', 'category': 'other'},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('file', resp.json()['errors'])

    def test_external_next_ignored(self):
        self.client.force_login(self.manager)
        resp = self.client.post(reverse('fleet:notifications_read'), {'all': '1', 'next': 'https://evil.example/'})
        self.assertEqual(resp['Location'], reverse('fleet:notifications'))


class VehicleWorkflowTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', password='x')
        self.client.force_login(self.user)
        self.driver = Driver.objects.create(name='Ahmad')

    def wizard_data(self, **extra):
        data = {'action': 'save', 'registration_no': 'wxy  9999', 'vehicle_type': 'van', 'make': 'Toyota',
                'model': 'Hiace', 'ownership_type': 'owned', 'status': 'active', 'seating_capacity': '12',
                'financier': 'Should be cleared', 'ins-provider': 'Etiqa', 'ins-expiry_date': str(TODAY + timedelta(days=200)),
                'ins-cost': '1500.00', 'rt-provider': 'JPJ', 'driver': self.driver.pk}
        data.update(extra)
        return data

    def test_wizard_creates_vehicle_with_related_records(self):
        resp = self.client.post(reverse('fleet:vehicle_create'), self.wizard_data())
        v = Vehicle.objects.get()
        self.assertRedirects(resp, v.get_absolute_url())
        self.assertEqual(v.registration_no, 'WXY 9999')
        self.assertEqual(v.financier, '')  # not applicable to owned vehicles
        self.assertEqual(v.compliance_records.count(), 1)  # road tax had no details beyond the JPJ default
        self.assertEqual(Expense.objects.get().amount, Decimal('1500.00'))
        self.assertEqual(v.primary_driver, self.driver)

    def test_wizard_requires_expiry_when_details_given(self):
        resp = self.client.post(reverse('fleet:vehicle_create'), self.wizard_data(**{'ins-expiry_date': ''}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Vehicle.objects.exists())
        self.assertTrue(resp.context['step_errors']['compliance'])

    def test_trailer_gets_no_driver_or_engine(self):
        self.client.post(reverse('fleet:vehicle_create'),
                         self.wizard_data(vehicle_type='trailer', engine_no='E1', odometer_km='5000'))
        v = Vehicle.objects.get()
        self.assertEqual((v.engine_no, v.odometer_km), ('', None))
        self.assertFalse(Assignment.objects.exists())

    def test_draft_save_and_resume(self):
        self.client.post(reverse('fleet:vehicle_create'), {'action': 'draft', 'make': 'Hino', 'step': '3'})
        draft = VehicleDraft.objects.get()
        self.assertEqual(draft.step, 3)
        resp = self.client.get(reverse('fleet:vehicle_create') + f'?draft={draft.pk}')
        self.assertEqual(resp.context['vform']['make'].value(), 'Hino')
        self.assertFalse(resp.context['vform'].is_bound)

    def test_renewal_creates_new_period_and_expense(self):
        v = make_vehicle()
        old = record(v, 'insurance', 5, workflow='in_progress')
        resp = self.client.post(reverse('fleet:compliance_renew', args=[v.pk, 'insurance']), {
            'provider': 'Allianz', 'start_date': str(old.expiry_date + timedelta(days=1)),
            'expiry_date': str(old.expiry_date + timedelta(days=365)), 'cost': '2100', 'record_expense': 'on',
            'payment_status': 'paid'})
        self.assertEqual(resp.status_code, 302)
        new = v.current_record('insurance')
        self.assertTrue(new.is_renewal)
        old.refresh_from_db()
        self.assertEqual(old.workflow, '')
        self.assertEqual(Expense.objects.get().category, 'insurance')

    def test_unknown_cost_is_not_zero(self):
        v = make_vehicle()
        self.client.post(reverse('fleet:compliance_renew', args=[v.pk, 'road_tax']),
                         {'expiry_date': str(TODAY + timedelta(days=300)), 'record_expense': 'on'})
        self.assertIsNone(v.current_record('road_tax').cost)
        self.assertFalse(Expense.objects.exists())
        self.assertContains(self.client.get(v.get_absolute_url() + '?tab=road_tax'), 'Cost not recorded')

    def test_breakdown_lifecycle(self):
        v = make_vehicle()
        self.client.post(reverse('fleet:breakdown_create'), {
            'vehicle': v.pk, 'reported_on': str(TODAY), 'problem': 'Overheating', 'severity': 'high',
            'take_off_road': 'on'})
        b = Breakdown.objects.get()
        v.refresh_from_db()
        self.assertEqual(v.status, 'maintenance')
        self.client.post(reverse('fleet:breakdown_progress', args=[b.pk]), {
            'status': 'completed', 'actual_cost': '800', 'workshop': 'Bengkel A', 'record_expense': 'on',
            'return_to_service': 'on'})
        b.refresh_from_db()
        v.refresh_from_db()
        self.assertEqual(b.completed_on, TODAY)
        self.assertEqual(v.status, 'active')
        self.assertEqual(b.expenses.get().amount, Decimal('800'))
        self.assertEqual(b.updates.count(), 2)

    def test_import_csv(self):
        csv = ('registration_no,vehicle_type,make,model,insurance_expiry\n'
               f'ABC 1,Truck / Lorry,Isuzu,NPR,{(TODAY + timedelta(days=90)):%d/%m/%Y}\n'
               ',car,Missing,Reg,\n')
        resp = self.client.post(reverse('fleet:vehicle_import'),
                                {'file': SimpleUploadedFile('v.csv', csv.encode(), content_type='text/csv')})
        self.assertEqual(len(resp.context['results']['created']), 1)
        self.assertEqual(len(resp.context['results']['errors']), 1)
        v = Vehicle.objects.get()
        self.assertEqual(v.vehicle_type, 'truck')
        self.assertIsNotNone(v.current_record('insurance'))

    def test_vehicle_filters(self):
        a, b = make_vehicle('AAA 1'), make_vehicle('BBB 2')
        record(a, 'insurance', -1)
        record(b, 'insurance', 200)
        resp = self.client.get(reverse('fleet:vehicle_list') + '?insurance=expired')
        self.assertEqual([v.registration_no for v in resp.context['page']], ['AAA 1'])


class PageRenderTests(TempMediaMixin, TestCase):
    PAGES = ['/', '/vehicles/', '/vehicles/new/', '/vehicles/import/', '/drivers/', '/drivers/new/', '/renewals/',
             '/renewals/?view=calendar', '/maintenance/', '/maintenance/breakdowns/new/', '/expenses/',
             '/expenses/?period=custom&start=2020-01-01&end=2030-01-01', '/expenses/new/', '/documents/',
             '/documents/upload/', '/reports/', '/reports/?report=fleet_register',
             '/reports/?report=expense_vehicle&period=ytd', '/reports/?report=expense_category',
             '/reports/?report=compliance', '/reports/?report=breakdowns', '/notifications/', '/settings/',
             '/search/?q=WXY', '/vehicles/?export=xlsx', '/expenses/?export=csv']

    def setUp(self):
        self.user = User.objects.create_superuser('admin', password='x')
        self.client.force_login(self.user)

    def test_empty_database(self):
        for url in self.PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get('/'), 'Start by adding your first vehicle')

    def test_with_sample_data(self):
        call_command('seed_demo', stdout=open(tempfile.mktemp(), 'w'))
        v = Vehicle.objects.first()
        b = Breakdown.objects.first()
        extra = [v.get_absolute_url(), f'{v.get_absolute_url()}?tab=history', f'/vehicles/{v.pk}/edit/',
                 f'/vehicles/{v.pk}/insurance/new/', b.get_absolute_url(), f'/drivers/{Driver.objects.first().pk}/']
        for url in self.PAGES + extra:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        with self.assertRaises(Exception):
            call_command('seed_demo')  # refuses to run twice
