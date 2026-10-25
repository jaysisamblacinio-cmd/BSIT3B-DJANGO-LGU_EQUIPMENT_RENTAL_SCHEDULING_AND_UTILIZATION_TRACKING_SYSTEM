from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.rentals.models import (
    Applicant, Equipment, EquipmentCategory, EquipmentRate, Payment,
    RentalRequest, RentalRequestItem, Reservation
)

User = get_user_model()


class RentalsWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_user', 'admin@lgu.gov.ph', 'pass1234')
        self.applicant_user = User.objects.create_user('farmer_test', 'farmer@test.com', 'pass1234')
        self.applicant = Applicant.objects.create(
            user=self.applicant_user,
            applicant_type='Farmer',
            address='Brgy San Isidro',
            valid_id_type="Driver's License",
            valid_id_number='N02-99-12345',
        )
        self.category = EquipmentCategory.objects.create(
            category_name='Agricultural Machinery',
            description='Farm tractors and rotavators'
        )
        self.equipment = Equipment.objects.create(
            equipment_code='TR-999',
            equipment_name='Kubota Farm Tractor 4WD',
            category=self.category,
            brand='Kubota',
            model='MU5502',
            condition_status='Good',
            availability_status='Available',
            current_location='Agri Depot',
        )
        self.rate = EquipmentRate.objects.create(
            equipment=self.equipment,
            rate_amount=Decimal('3500.00'),
            rate_unit='Day',
            is_active=1,
        )

    def test_equipment_catalog_page_renders(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('rentals:equipment_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'TR-999')
        self.assertContains(res, 'Kubota Farm Tractor 4WD')

    def test_rental_request_and_conflict_detection(self):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(days=2)

        # 1. Test availability check
        is_avail, _ = self.equipment.is_available_for_dates(start, end)
        self.assertTrue(is_avail)

        # 2. Submit rental request
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Corn field land preparation',
            project_location='Sitio Mabuhay',
            requested_start=start,
            requested_end=end,
            status='Pending',
        )
        RentalRequestItem.objects.create(
            request=req,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('7000.00'),
        )
        self.assertEqual(req.total_estimated_cost, Decimal('7000.00'))

        # 3. Approve request via AJAX
        self.client.force_login(self.admin)
        action_res = self.client.post(reverse('rentals:request_action_ajax', args=[req.id]), {
            'action': 'approve',
            'remarks': 'Approved for corn harvest season',
        })
        self.assertEqual(action_res.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.reservations.count(), 1)

        # 4. Equipment now has reservation - overlapping dates must trigger conflict!
        is_avail_conflict, _ = self.equipment.is_available_for_dates(start + timedelta(hours=4), end - timedelta(hours=4))
        self.assertFalse(is_avail_conflict)

    def test_payment_and_receipt(self):
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Drainage excavation',
            project_location='Poblacion',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Approved',
        )
        pay = Payment.objects.create(
            request=req,
            amount=Decimal('3500.00'),
            payment_type='Rental Fee',
            payment_method='Cash',
            reference_or_no='OR-TEST-001',
            payment_status='Paid',
            recorded_by=self.admin,
        )

        self.client.force_login(self.admin)
        receipt_res = self.client.get(reverse('rentals:payment_receipt', args=[pay.id]))
        self.assertEqual(receipt_res.status_code, 200)
        self.assertContains(receipt_res, 'OR-TEST-001')
        self.assertContains(receipt_res, '3,500.00')

    def test_excel_export_generation(self):
        self.client.force_login(self.admin)
        for r_type in ['transactions', 'utilization', 'revenue', 'maintenance']:
            res = self.client.get(reverse('rentals:export_report_excel', args=[r_type]))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.assertGreater(len(res.content), 1000)
