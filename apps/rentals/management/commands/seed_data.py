from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.rentals.models import (
    EquipmentCategory, Equipment, EquipmentRate,
    Role, Applicant, RentalRequest, RentalRequestItem,
    Reservation, EquipmentAssignment, UtilizationLog,
    MaintenanceRecord, Payment, Notification
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial LGU Equipment Rental data, categories, equipment, rates, and demo accounts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding LGU Equipment Rental System data..."))

        # 1. Create Roles and Auth Groups
        roles_data = [
            ('Admin', 'Full administrative control and master settings'),
            ('Equipment Officer', 'Manages machinery inventory, approvals, and scheduling'),
            ('Finance Officer', 'Issues receipts, processes rental collections, and verifies payments'),
            ('Equipment Operator', 'Assigned to machinery in the field, logs hours and fuel'),
            ('Applicant', 'Citizen, farmer, cooperative, or contractor renting LGU machinery'),
        ]
        for name, desc in roles_data:
            Role.objects.get_or_create(role_name=name, defaults={'description': desc})
            Group.objects.get_or_create(name=name)

        # 2. Demo User Accounts
        demo_users = [
            ('ADMIN12', 'System', 'Admin', 'admin12@lgu.gov.ph', 'Admin', True, True),
            ('glenn', 'Glenn', 'Administrator', 'admin@lgu.gov.ph', 'Admin', True, True),
            ('officer', 'Engr. Roberto', 'Mercado', 'officer@lgu.gov.ph', 'Equipment Officer', False, True),
            ('finance', 'Ma. Lourdes', 'Santos', 'treasury@lgu.gov.ph', 'Finance Officer', False, False),
            ('danilo_operator', 'Danilo', 'Reyes', 'operator@lgu.gov.ph', 'Equipment Operator', False, False),
            ('farmer_juan', 'Juan', 'dela Cruz', 'juan@agricoop.ph', 'Applicant', False, False),
            ('contractor_mateo', 'Mateo', 'Villanueva', 'build@mvcon.com', 'Applicant', False, False),
        ]

        created_users = {}
        for username, fname, lname, email, role_name, is_super, is_staff in demo_users:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': fname,
                    'last_name': lname,
                    'email': email,
                    'is_superuser': is_super,
                    'is_staff': is_staff,
                }
            )
            if created or not u.password:
                u.set_password('pass1234')
                u.save()
            grp = Group.objects.get(name=role_name)
            u.groups.add(grp)
            created_users[username] = u

        # 3. Applicant Profiles
        Applicant.objects.get_or_create(
            user=created_users['farmer_juan'],
            defaults={
                'applicant_type': 'Farmer',
                'organization_name': 'San Isidro Farmers Agricultural Cooperative',
                'address': 'Brgy. San Isidro, Municipal Agri District',
                'valid_id_type': 'Farmer Fisherfolk Registry System (RSBSA)',
                'valid_id_number': 'RSBSA-02-137-00918',
            }
        )
        contractor_app, _ = Applicant.objects.get_or_create(
            user=created_users['contractor_mateo'],
            defaults={
                'applicant_type': 'Contractor',
                'organization_name': 'MV Builders & General Construction',
                'address': 'Poblacion Commercial Complex, National Highway',
                'valid_id_type': 'PCAB License / PRC Engineering ID',
                'valid_id_number': 'PCAB-LIC-2024-5589',
                'tin_number': '412-887-321-000',
            }
        )

        # 4. Equipment Categories
        categories_data = [
            ('Heavy Earthmoving & Construction', 'Excavators, backhoes, bulldozers, and heavy civil works equipment'),
            ('Road Maintenance & Compaction', 'Road rollers, motor graders, and asphalt pavers'),
            ('Agricultural Machinery', 'Tractors, rotavators, harvesters, and irrigation pumps'),
            ('Hauling & Logistics Trucks', 'Heavy dump trucks, cargo flatbeds, and water tankers'),
            ('Disaster Response & Power', 'Emergency generator sets, mobile pumps, and rescue cranes'),
        ]
        created_cats = {}
        for cname, cdesc in categories_data:
            cat, _ = EquipmentCategory.objects.get_or_create(category_name=cname, defaults={'description': cdesc})
            created_cats[cname] = cat

        # 5. Master Equipment Inventory
        equipment_list = [
            {
                'code': 'EXC-001',
                'name': 'Komatsu PC200-8 Hydraulic Excavator',
                'cat': 'Heavy Earthmoving & Construction',
                'brand': 'Komatsu',
                'model': 'PC200-8 Galeo',
                'plate': 'SJP-492',
                'condition': 'Excellent',
                'status': 'Available',
                'rate': Decimal('8500.00'),
                'unit': 'Day',
                'location': 'Municipal Motorpool Depot, Bay 1',
            },
            {
                'code': 'BKH-002',
                'name': 'Caterpillar 426F2 4WD Backhoe Loader',
                'cat': 'Heavy Earthmoving & Construction',
                'brand': 'Caterpillar',
                'model': '426F2 Tier 4',
                'plate': 'SHX-881',
                'condition': 'Good',
                'status': 'Available',
                'rate': Decimal('6000.00'),
                'unit': 'Day',
                'location': 'Municipal Motorpool Depot, Bay 3',
            },
            {
                'code': 'MGR-003',
                'name': 'Mitsubishi MG330 Motor Road Grader',
                'cat': 'Road Maintenance & Compaction',
                'brand': 'Mitsubishi',
                'model': 'MG330',
                'plate': 'SGY-204',
                'condition': 'Good',
                'status': 'Available',
                'rate': Decimal('7000.00'),
                'unit': 'Day',
                'location': 'Barangay Road Works Substation',
            },
            {
                'code': 'RLL-004',
                'name': 'Bomag BW211 D-40 Single Drum Vibratory Roller',
                'cat': 'Road Maintenance & Compaction',
                'brand': 'Bomag',
                'model': 'BW211 D-40',
                'plate': 'SFL-903',
                'condition': 'Good',
                'status': 'Available',
                'rate': Decimal('5500.00'),
                'unit': 'Day',
                'location': 'Municipal Motorpool Depot, Bay 4',
            },
            {
                'code': 'TRC-005',
                'name': 'Kubota MU5502 4WD Heavy Farm Tractor',
                'cat': 'Agricultural Machinery',
                'brand': 'Kubota',
                'model': 'MU5502 4WD',
                'plate': 'AGR-101',
                'condition': 'Excellent',
                'status': 'Available',
                'rate': Decimal('3500.00'),
                'unit': 'Day',
                'location': 'Agri Services Staging Center',
            },
            {
                'code': 'DMP-006',
                'name': 'Isuzu Giga 10-Wheeler Heavy Dump Truck',
                'cat': 'Hauling & Logistics Trucks',
                'brand': 'Isuzu',
                'model': 'Giga CYZ52',
                'plate': 'NAA-6712',
                'condition': 'Good',
                'status': 'Available',
                'rate': Decimal('4500.00'),
                'unit': 'Day',
                'location': 'Engineering Materials Depot',
            },
            {
                'code': 'GEN-007',
                'name': 'Cummins 150kVA Mobile Silent Diesel Generator',
                'cat': 'Disaster Response & Power',
                'brand': 'Cummins',
                'model': 'C150D5e',
                'plate': 'DRR-305',
                'condition': 'Excellent',
                'status': 'Available',
                'rate': Decimal('4000.00'),
                'unit': 'Day',
                'location': 'MDRRMO Emergency Rescue Center',
            },
        ]

        for eq_data in equipment_list:
            eq, created = Equipment.objects.get_or_create(
                equipment_code=eq_data['code'],
                defaults={
                    'equipment_name': eq_data['name'],
                    'category': created_cats[eq_data['cat']],
                    'brand': eq_data['brand'],
                    'model': eq_data['model'],
                    'plate_number': eq_data['plate'],
                    'condition_status': eq_data['condition'],
                    'availability_status': eq_data['status'],
                    'current_location': eq_data['location'],
                }
            )
            EquipmentRate.objects.get_or_create(
                equipment=eq,
                rate_amount=eq_data['rate'],
                rate_unit=eq_data['unit'],
                defaults={'is_active': 1}
            )

        # 6. Sample Request and Payment for demonstration
        if not RentalRequest.objects.exists():
            excavator = Equipment.objects.get(equipment_code='EXC-001')
            now = timezone.now()
            sample_req = RentalRequest.objects.create(
                applicant=contractor_app,
                purpose='Drainage excavation and municipal road slope rehabilitation',
                project_location='Sitio Centro, Barangay San Isidro',
                requested_start=now + timedelta(days=1),
                requested_end=now + timedelta(days=3),
                status='Approved',
                reviewed_by=created_users['officer'],
                reviewed_at=now,
                review_remarks='Approved per municipal engineering schedule. Coordinate dispatch with operator.',
            )
            RentalRequestItem.objects.create(
                request=sample_req,
                equipment=excavator,
                quantity=1,
                estimated_rate=Decimal('8500.00'),
                subtotal=Decimal('17000.00'),
            )
            Reservation.objects.create(
                request=sample_req,
                equipment=excavator,
                scheduled_start=now + timedelta(days=1),
                scheduled_end=now + timedelta(days=3),
                status='Scheduled',
                approved_by=created_users['officer'],
            )
            pay = Payment.objects.create(
                request=sample_req,
                amount=Decimal('17000.00'),
                payment_type='Rental Fee',
                payment_method='Cash',
                reference_or_no='OR-2026-LGU-001',
                payment_status='Paid',
                recorded_by=created_users['finance'],
                remarks='Full rental fee payment collected for Sitio Centro drainage project.',
            )
            Notification.objects.create(
                user=created_users['contractor_mateo'],
                title='Application Approved & OR Issued',
                message=f'Your rental request REQ-#{sample_req.id:04d} has been approved with Official Receipt OR-2026-LGU-001.',
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded LGU equipment, categories, rates, and demo accounts!"))
