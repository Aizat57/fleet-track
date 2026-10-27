"""Fill an EMPTY database with sample fleet data for training or a demo.

Never run this against a production database: it refuses if any vehicle already exists.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from fleet.models import (Activity, Assignment, Breakdown, BreakdownUpdate, ComplianceRecord, Department, Driver,
                          Expense, Location, ServiceTask, Vehicle)

VEHICLES = [
    ('WXY 1234', 'car', 'Proton', 'X70', 2022), ('VBN 4521', 'car', 'Toyota', 'Camry', 2021),
    ('BMK 7782', 'van', 'Toyota', 'Hiace', 2020), ('WTA 3390', 'van', 'Nissan', 'NV350', 2019),
    ('JRP 6610', 'bus', 'Hino', 'RK8J', 2018), ('WPL 2045', 'truck', 'Isuzu', 'NPR 75', 2021),
    ('BQT 9087', 'truck', 'Hino', '500 FG', 2017), ('PKD 5521', 'prime_mover', 'Volvo', 'FH 460', 2020),
    ('WVG 8103', 'prime_mover', 'Scania', 'G410', 2019), ('TRL 4412', 'trailer', 'Sin Heng', '40ft Flatbed', 2019),
    ('TRL 4413', 'trailer', 'Sin Heng', '40ft Skeletal', 2020), ('VCE 1180', 'car', 'Perodua', 'Bezza', 2023),
]
DRIVERS = ['Ahmad Faizal bin Rahman', 'Siti Nurhaliza binti Omar', 'Rajesh Kumar a/l Muthu', 'Lim Wei Jie',
           'Mohd Hafiz bin Ismail', 'Nurul Aina binti Zakaria', 'Tan Chee Keong', 'Muhammad Danial bin Azmi']


class Command(BaseCommand):
    help = 'Populate an empty database with sample vehicles, drivers, renewals, breakdowns and expenses.'

    def add_arguments(self, parser):
        parser.add_argument('--vehicles', type=int, default=len(VEHICLES),
                            help=f'How many sample vehicles to create (5–{len(VEHICLES)}).')

    def handle(self, *args, **opts):
        count = opts['vehicles']
        if not 5 <= count <= len(VEHICLES):
            raise CommandError(f'--vehicles must be between 5 and {len(VEHICLES)}.')
        if Vehicle.objects.exists():
            raise CommandError('Vehicles already exist. seed_demo only runs on an empty database.')
        rnd = random.Random(7)
        today = timezone.localdate()
        user = get_user_model().objects.filter(is_superuser=True).first()

        depts = [Department.objects.get_or_create(name=n)[0] for n in ('Logistics', 'Sales', 'Operations', 'Admin')]
        locs = [Location.objects.get_or_create(name=n)[0] for n in ('Shah Alam HQ', 'Port Klang Depot', 'Johor Bahru')]
        drivers = [Driver.objects.create(name=n, staff_no=f'EMP{100 + i}', phone=f'01{rnd.randint(2, 9)}-{rnd.randint(1000000, 9999999)}',
                                         licence_classes=rnd.choice(['D', 'D, E', 'D, E, GDL']), department=rnd.choice(depts),
                                         licence_no=f'{rnd.randint(10000000, 99999999)}',
                                         licence_expiry=today + timedelta(days=rnd.randint(-10, 900)))
                   for i, n in enumerate(DRIVERS)]
        # Ordered so even a small sample covers every operational status.
        statuses = ['active', 'active', 'maintenance', 'active', 'active', 'active', 'out_of_service', 'active',
                    'available', 'maintenance', 'active', 'active']
        # Expiry offsets chosen to exercise every state: expired, ≤7, ≤30, ≤60 and comfortably valid.
        ins_offsets = [-12, 5, 21, 44, 120, 200, 300, 18, 2, 90, 160, -3]
        rt_offsets = [150, -6, 26, 58, 240, 3, 330, 75, 12, 210, 45, 280]
        for i, (reg, vtype, make, model, year) in enumerate(VEHICLES[:count]):
            v = Vehicle.objects.create(
                registration_no=reg, vehicle_type=vtype, make=make, model=model, year=year, status=statuses[i],
                department=rnd.choice(depts), location=rnd.choice(locs), created_by=user,
                fuel_type='' if vtype == 'trailer' else ('petrol' if vtype == 'car' else 'diesel'),
                odometer_km=None if vtype == 'trailer' else rnd.randint(20000, 380000),
                ownership_type=rnd.choice(['owned', 'owned', 'financed', 'leased']),
                registered_owner='Syarikat Contoh Logistik Sdn Bhd')
            for kind, offset, provider, cost in (
                    ('insurance', ins_offsets[i], rnd.choice(['Etiqa', 'Allianz', 'Takaful Malaysia', 'AmGeneral']),
                     Decimal(rnd.randint(1200, 9800))),
                    ('road_tax', rt_offsets[i], 'JPJ', Decimal(rnd.choice([90, 280, 380, 1200, 2400])))):
                exp = today + timedelta(days=offset)
                ComplianceRecord.objects.create(kind=kind, vehicle=v, provider=provider, expiry_date=exp,
                                                start_date=exp - timedelta(days=364), cost=cost, responsible=user,
                                                reference_no=f'{kind[:3].upper()}-{rnd.randint(100000, 999999)}',
                                                coverage='Comprehensive' if kind == 'insurance' else '',
                                                created_by=user)
            if vtype != 'trailer':
                Assignment.objects.create(vehicle=v, driver=drivers[i % len(drivers)], start_date=today - timedelta(days=200))
            Activity.objects.create(actor=user, verb='vehicle_added', message=f'Vehicle {reg} added', vehicle=v,
                                    url=v.get_absolute_url(), created_at=timezone.now() - timedelta(days=60 - i))

        vehicles = list(Vehicle.objects.all())
        suppliers = {'fuel': ['Petronas', 'Shell', 'Petron'], 'maintenance': ['Bengkel Maju Jaya', 'AutoCare Shah Alam'],
                     'repair': ['Bengkel Maju Jaya', 'Hino Service Centre'], 'tyres': ['Tyre Plus'],
                     'toll_parking': ['PLUS Malaysia'], 'other': ['Various']}
        for m in range(11, -1, -1):
            month_day = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
            for _ in range(rnd.randint(14, 24)):
                cat = rnd.choice(['fuel'] * 5 + ['maintenance', 'repair', 'tyres', 'toll_parking', 'other'])
                d = month_day + timedelta(days=rnd.randint(0, 27))
                if d > today:
                    d = today
                v = rnd.choice(vehicles)
                amount = {'fuel': (150, 900), 'maintenance': (300, 2500), 'repair': (400, 6500), 'tyres': (600, 4800),
                          'toll_parking': (20, 300), 'other': (50, 600)}[cat]
                Expense.objects.create(vehicle=v, date=d, category=cat, description=f'{cat.replace("_", " ").title()} – {v}',
                                       supplier=rnd.choice(suppliers[cat]), amount=Decimal(rnd.randint(*amount)),
                                       payment_status='outstanding' if m == 0 and rnd.random() < .25 else 'paid',
                                       created_by=user)
        Expense.objects.create(vehicle=vehicles[7], date=today + timedelta(days=40), category='tyres',
                               description='Planned tyre replacement (6 tyres)', supplier='Tyre Plus',
                               amount=Decimal('5400'), payment_status='forecast', created_by=user)

        for v, problem, sev, status in ((vehicles[7], 'Engine overheating on highway', 'critical', 'in_repair'),
                                        (vehicles[6], 'Air brake pressure warning', 'high', 'awaiting_parts'),
                                        (vehicles[3], 'Aircond not cold', 'low', 'completed')):
            b = Breakdown.objects.create(vehicle=v, problem=problem, severity=sev, status=status, reported_by=user,
                                         reported_on=today - timedelta(days=rnd.randint(2, 12)),
                                         workshop='Hino Service Centre', estimated_cost=Decimal(rnd.randint(800, 5000)),
                                         completed_on=today if status == 'completed' else None)
            BreakdownUpdate.objects.create(breakdown=b, status='reported', user=user, note='Reported by driver.',
                                           created_at=timezone.now() - timedelta(days=5))
            BreakdownUpdate.objects.create(breakdown=b, status=status, user=user, note='Workshop update.')
            Activity.objects.create(actor=user, verb='breakdown_reported', message=f'{b.get_severity_display()} breakdown reported for {v}: {problem}',
                                    vehicle=v, url=b.get_absolute_url())
        ServiceTask.objects.create(vehicle=vehicles[5], title='20,000 km service', due_date=today - timedelta(days=4))
        ServiceTask.objects.create(vehicle=vehicles[4], title='PUSPAKOM inspection', due_date=today + timedelta(days=9))
        self.stdout.write(self.style.SUCCESS(f'Sample data created: {len(vehicles)} vehicles, {len(drivers)} drivers.'))
