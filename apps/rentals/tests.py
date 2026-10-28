from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.rentals.models import (
    Applicant, Equipment, EquipmentCategory, EquipmentRate, Payment,
    Notification, RentalRequest, RentalRequestItem, Reservation
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

    def test_seed_command_does_not_create_demo_accounts_or_sample_rentals(self):
        call_command('seed_data', verbosity=0)

        demo_usernames = (
            'ADMIN12',
            'glenn',
            'officer',
            'finance',
            'danilo_operator',
            'farmer_juan',
            'contractor_mateo',
        )
        self.assertFalse(User.objects.filter(username__in=demo_usernames).exists())
        self.assertFalse(RentalRequest.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_rented_equipment_page_shows_approved_rentals(self):
        start = timezone.now() + timedelta(days=2)
        approved_request = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Road repair',
            project_location='North District',
            requested_start=start,
            requested_end=start + timedelta(days=2),
            status='Approved',
        )
        RentalRequestItem.objects.create(
            request=approved_request,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('7000.00'),
        )
        pending_request = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Pending work',
            project_location='South District',
            requested_start=start,
            requested_end=start + timedelta(days=1),
            status='Pending',
        )
        RentalRequestItem.objects.create(
            request=pending_request,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('3500.00'),
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('rentals:rented_equipment'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REQ-%04d' % approved_request.pk)
        self.assertContains(response, 'Kubota Farm Tractor 4WD')
        self.assertContains(response, 'North District')
        self.assertNotContains(response, 'South District')

    def test_applicant_rented_equipment_page_shows_only_own_rentals(self):
        start = timezone.now() + timedelta(days=2)
        own_request = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Own rental',
            project_location='Applicant District',
            requested_start=start,
            requested_end=start + timedelta(days=1),
            status='Approved',
        )
        RentalRequestItem.objects.create(
            request=own_request,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('3500.00'),
        )

        other_user = User.objects.create_user('other_farmer', password='pass1234')
        other_applicant = Applicant.objects.create(
            user=other_user,
            applicant_type='Farmer',
            address='Other address',
            valid_id_type='Government ID',
            valid_id_number='OTHER-123',
        )
        other_request = RentalRequest.objects.create(
            applicant=other_applicant,
            purpose='Other rental',
            project_location='Private District',
            requested_start=start,
            requested_end=start + timedelta(days=1),
            status='Approved',
        )
        RentalRequestItem.objects.create(
            request=other_request,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('3500.00'),
        )

        self.client.force_login(self.applicant_user)
        response = self.client.get(reverse('rentals:rented_equipment'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Rented Equipment')
        self.assertContains(response, 'Applicant District')
        self.assertNotContains(response, 'Private District')
        self.assertContains(response, 'My Rented Equipment</span>')

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

    def test_application_notifies_admin_group_member(self):
        admin_group = Group.objects.create(name='Admin')
        admin_user = User.objects.create_user(
            username='group_admin',
            email='group_admin@example.com',
            password='pass1234',
        )
        admin_user.groups.add(admin_group)

        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(days=1)
        self.client.force_login(self.applicant_user)
        response = self.client.post(reverse('rentals:apply_rental'), {
            'equipment_ids': [self.equipment.pk],
            'requested_start': start.isoformat(),
            'requested_end': end.isoformat(),
            'purpose': 'Prepare farmland',
            'project_location': 'Barangay San Isidro',
            'applicant_type': 'Farmer',
        })

        self.assertRedirects(response, reverse('rentals:my_requests'))
        notification = Notification.objects.get(user=admin_user)
        self.assertIn('New Rental Application', notification.title)
        self.assertIn(self.equipment.equipment_code, notification.message)

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
