from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from apps.rentals.models import (
    EquipmentCategory, Equipment, EquipmentRate,
    Role,
)


class Command(BaseCommand):
    help = 'Seeds LGU equipment roles, categories, inventory, and rates'

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

        # 2. Equipment Categories
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

        # 3. Master Equipment Inventory
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

        self.stdout.write(self.style.SUCCESS("Successfully seeded LGU roles, equipment, categories, and rates."))
