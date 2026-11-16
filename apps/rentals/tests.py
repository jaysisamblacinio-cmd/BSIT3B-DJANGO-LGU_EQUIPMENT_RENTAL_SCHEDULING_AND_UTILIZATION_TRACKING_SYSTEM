from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.rentals.models import (
    Applicant, Equipment, EquipmentAssignment, EquipmentCategory, EquipmentRate, Payment,
    MaintenanceRecord, Notification, RentalRequest, RentalRequestItem, Reservation
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

    def test_equipment_photo_upload_and_display(self):
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='green').save(image_buffer, format='PNG')
        image_buffer.seek(0)
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.client.force_login(self.admin)
                response = self.client.post(reverse('rentals:equipment_save_ajax'), {
                    'equipment_code': 'TR-PHOTO',
                    'equipment_name': 'Photo Test Tractor',
                    'category_id': self.category.pk,
                    'photo': SimpleUploadedFile(
                        'tractor.png',
                        image_buffer.getvalue(),
                        content_type='image/png',
                    ),
                })

                self.assertEqual(response.status_code, 200)
                self.equipment.refresh_from_db()
                uploaded_equipment = Equipment.objects.get(equipment_code='TR-PHOTO')
                self.assertTrue(uploaded_equipment.photo.startswith('equipment/photos/'))
                self.assertTrue((Path(media_root) / uploaded_equipment.photo).is_file())
                self.assertEqual(uploaded_equipment.photo_url, f'/media/{uploaded_equipment.photo}')

                catalog = self.client.get(reverse('rentals:equipment_list'))
                self.assertContains(catalog, uploaded_equipment.photo_url)
                application = self.client.get(reverse('rentals:apply_rental'))
                self.assertContains(application, uploaded_equipment.photo_url)

    def test_equipment_photo_upload_rejects_non_image(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('rentals:equipment_save_ajax'), {
            'equipment_code': 'TR-BADPHOTO',
            'equipment_name': 'Bad Photo Test',
            'category_id': self.category.pk,
            'photo': SimpleUploadedFile(
                'not-an-image.png',
                b'not an image',
                content_type='image/png',
            ),
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Equipment.objects.filter(equipment_code='TR-BADPHOTO').exists())

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

    def test_seed_command_tolerates_duplicate_existing_equipment_rates(self):
        category = EquipmentCategory.objects.create(
            category_name='Road Maintenance & Compaction',
        )
        equipment = Equipment.objects.create(
            equipment_code='MGR-003',
            equipment_name='Existing Motor Road Grader',
            category=category,
        )
        for _ in range(2):
            EquipmentRate.objects.create(
                equipment=equipment,
                rate_amount=Decimal('7000.00'),
                rate_unit='Day',
            )

        call_command('seed_data', verbosity=0)

        self.assertEqual(
            EquipmentRate.objects.filter(
                equipment=equipment,
                rate_amount=Decimal('7000.00'),
                rate_unit='Day',
            ).count(),
            2,
        )

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

    def test_equipment_needing_repair_is_unavailable_and_listed_for_maintenance(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('rentals:equipment_save_ajax'), {
            'id': self.equipment.pk,
            'equipment_code': self.equipment.equipment_code,
            'equipment_name': self.equipment.equipment_name,
            'category_id': self.category.pk,
            'condition_status': 'Needs Repair',
            'availability_status': 'Available',
        })

        self.assertEqual(response.status_code, 200)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.availability_status, 'Under Maintenance')
        repair_record = MaintenanceRecord.objects.get(equipment=self.equipment)
        self.assertEqual(repair_record.status, 'In Progress')

        start = timezone.now() + timedelta(days=2)
        available, reason = self.equipment.is_available_for_dates(start, start + timedelta(days=1))
        self.assertFalse(available)
        self.assertIn('needs repair', reason)

        start = timezone.now() + timedelta(days=2)
        application_response = self.client.post(reverse('rentals:apply_rental'), {
            'equipment_ids': [self.equipment.pk],
            'requested_start': start.isoformat(),
            'requested_end': (start + timedelta(days=1)).isoformat(),
            'purpose': 'Prepare farmland',
            'project_location': 'Barangay San Isidro',
            'payment_method': 'Cash',
        })
        self.assertRedirects(application_response, reverse('rentals:apply_rental'))
        self.assertFalse(RentalRequest.objects.exists())

        maintenance_page = self.client.get(reverse('rentals:maintenance_list'))
        self.assertContains(maintenance_page, self.equipment.equipment_code)
        application_page = self.client.get(reverse('rentals:apply_rental'))
        self.assertNotContains(application_page, self.equipment.equipment_code)

    def test_returning_equipment_needing_repair_creates_maintenance_record(self):
        start = timezone.now() - timedelta(days=1)
        rental_request = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Road repair',
            project_location='North District',
            requested_start=start,
            requested_end=timezone.now() + timedelta(days=1),
            status='Released',
        )
        reservation = Reservation.objects.create(
            request=rental_request,
            equipment=self.equipment,
            scheduled_start=start,
            scheduled_end=timezone.now() + timedelta(days=1),
            status='In Progress',
            approved_by=self.admin,
        )
        assignment = EquipmentAssignment.objects.create(
            reservation=reservation,
            equipment=self.equipment,
            status='Released',
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('rentals:equipment_return_ajax', args=[assignment.pk]),
            {
                'equipment_condition': 'Needs Repair',
                'condition_after': 'Hydraulic hose leaking.',
                'work_description': 'Inspect and replace the damaged hose.',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.availability_status, 'Under Maintenance')
        repair_record = MaintenanceRecord.objects.get(equipment=self.equipment)
        self.assertEqual(repair_record.status, 'In Progress')
        self.assertEqual(repair_record.problem_reported, 'Hydraulic hose leaking.')

    def test_equipment_is_available_only_after_maintenance_is_completed(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('rentals:equipment_save_ajax'), {
            'id': self.equipment.pk,
            'equipment_code': self.equipment.equipment_code,
            'equipment_name': self.equipment.equipment_name,
            'category_id': self.category.pk,
            'condition_status': 'Needs Repair',
            'availability_status': 'Under Maintenance',
        })
        repair_record = MaintenanceRecord.objects.get(equipment=self.equipment)

        self.client.post(reverse('rentals:equipment_save_ajax'), {
            'id': self.equipment.pk,
            'equipment_code': self.equipment.equipment_code,
            'equipment_name': self.equipment.equipment_name,
            'category_id': self.category.pk,
            'condition_status': 'Good',
            'availability_status': 'Available',
        })
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.availability_status, 'Under Maintenance')

        response = self.client.post(reverse('rentals:maintenance_save_ajax'), {
            'id': repair_record.pk,
            'equipment_id': self.equipment.pk,
            'maintenance_type': 'Corrective',
            'problem_reported': repair_record.problem_reported,
            'description': 'Replaced damaged hydraulic hose.',
            'technician_name': 'Motorpool Technician',
            'cost': '250.00',
            'scheduled_date': timezone.now().date().isoformat(),
            'status': 'Completed',
        })

        self.assertEqual(response.status_code, 200)
        self.equipment.refresh_from_db()
        repair_record.refresh_from_db()
        self.assertEqual(repair_record.status, 'Completed')
        self.assertIsNotNone(repair_record.completed_date)
        self.assertEqual(self.equipment.condition_status, 'Good')
        self.assertEqual(self.equipment.availability_status, 'Available')
        start = timezone.now() + timedelta(days=2)
        self.assertTrue(self.equipment.is_available_for_dates(start, start + timedelta(days=1))[0])

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
            'payment_method': 'Maya',
        })

        rental_request = RentalRequest.objects.get(applicant=self.applicant)
        self.assertRedirects(
            response,
            reverse('rentals:customer_payment', args=[rental_request.pk]),
        )
        self.assertEqual(rental_request.preferred_payment_method, 'Maya')
        self.assertContains(self.client.get(response.url), 'Application awaiting review')
        notification = Notification.objects.get(user=admin_user)
        self.assertIn('New Rental Application', notification.title)
        self.assertIn(self.equipment.equipment_code, notification.message)

    def test_application_payment_method_is_required_to_be_valid(self):
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
            'payment_method': 'Unknown',
        })

        self.assertRedirects(response, reverse('rentals:apply_rental'))
        self.assertFalse(RentalRequest.objects.exists())

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

    def test_customer_can_submit_payment_for_pending_request(self):
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Drainage excavation',
            project_location='Poblacion',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Pending',
            preferred_payment_method='Maya',
        )
        RentalRequestItem.objects.create(
            request=req,
            equipment=self.equipment,
            quantity=1,
            estimated_rate=Decimal('3500.00'),
            subtotal=Decimal('3500.00'),
        )
        self.client.force_login(self.applicant_user)

        page = self.client.get(reverse('rentals:customer_payment', args=[req.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Maya')
        self.assertContains(page, 'Application awaiting review')
        applications_page = self.client.get(reverse('rentals:my_requests'))
        self.assertContains(applications_page, reverse('rentals:customer_payment', args=[req.pk]))
        response = self.client.post(reverse('rentals:customer_payment', args=[req.pk]), {
            'amount': '2500.00',
            'payment_method': 'Maya',
            'transaction_reference': 'MAYA-REF-100',
            'confirm_payment': 'on',
        })

        self.assertRedirects(response, reverse('rentals:my_requests'))
        payment = Payment.objects.get(request=req)
        self.assertEqual(payment.payment_status, 'Pending')
        self.assertEqual(payment.payment_method, 'Maya')
        self.assertEqual(payment.transaction_reference, 'MAYA-REF-100')
        self.assertIsNone(payment.reference_or_no)
        applications_page = self.client.get(reverse('rentals:my_requests'))
        self.assertContains(applications_page, 'awaiting Treasury verification')

    def test_customer_cannot_pay_unapproved_or_another_applicants_request(self):
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Drainage excavation',
            project_location='Poblacion',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Rejected',
        )
        self.client.force_login(self.applicant_user)

        response = self.client.get(reverse('rentals:customer_payment', args=[req.pk]))
        self.assertRedirects(response, reverse('rentals:my_requests'))

        another_user = User.objects.create_user('another_farmer', password='pass1234')
        another_applicant = Applicant.objects.create(
            user=another_user,
            applicant_type='Farmer',
            address='Other address',
            valid_id_type='Government ID',
            valid_id_number='OTHER-456',
        )
        another_req = RentalRequest.objects.create(
            applicant=another_applicant,
            purpose='Other work',
            project_location='Other location',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Approved',
        )
        response = self.client.get(reverse('rentals:customer_payment', args=[another_req.pk]))
        self.assertEqual(response.status_code, 404)

    def test_finance_verifies_customer_payment_and_issues_receipt(self):
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Drainage excavation',
            project_location='Poblacion',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Approved',
        )
        payment = Payment.objects.create(
            request=req,
            amount=Decimal('3500.00'),
            payment_type='Rental Fee',
            payment_method='Maya',
            transaction_reference='MAYA-REF-101',
            payment_status='Pending',
            recorded_by=self.applicant_user,
        )
        self.client.force_login(self.admin)
        payment_list = self.client.get(reverse('rentals:payment_list'))
        self.assertContains(payment_list, 'MAYA-REF-101')
        self.assertContains(payment_list, 'Verify')

        response = self.client.post(reverse('rentals:payment_verify_ajax', args=[payment.pk]))

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, 'Paid')
        self.assertTrue(payment.reference_or_no.startswith('OR-'))
        self.assertEqual(payment.transaction_reference, 'MAYA-REF-101')

    def test_payment_form_includes_maya_method(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('rentals:payment_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="Maya">Maya</option>', html=True)

    def test_payment_save_accepts_maya_and_rejects_unknown_methods(self):
        req = RentalRequest.objects.create(
            applicant=self.applicant,
            purpose='Drainage excavation',
            project_location='Poblacion',
            requested_start=timezone.now() + timedelta(days=1),
            requested_end=timezone.now() + timedelta(days=2),
            status='Approved',
        )
        self.client.force_login(self.admin)
        payment_data = {
            'request_id': req.pk,
            'amount': '3500.00',
            'payment_type': 'Rental Fee',
            'payment_method': 'Maya',
        }

        response = self.client.post(reverse('rentals:payment_save_ajax'), payment_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.get(pk=response.json()['id']).payment_method, 'Maya')

        payment_data['payment_method'] = 'Unknown'
        response = self.client.post(reverse('rentals:payment_save_ajax'), payment_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Payment.objects.count(), 1)

    def test_excel_export_generation(self):
        self.client.force_login(self.admin)
        for r_type in ['transactions', 'utilization', 'revenue', 'maintenance']:
            res = self.client.get(reverse('rentals:export_report_excel', args=[r_type]))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.assertGreater(len(res.content), 1000)
