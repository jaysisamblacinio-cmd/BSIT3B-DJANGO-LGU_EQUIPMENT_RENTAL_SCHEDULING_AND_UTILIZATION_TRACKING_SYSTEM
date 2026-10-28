from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.rentals.models import Applicant


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='management_admin',
            email='admin@example.com',
            password='AdminPass123!',
        )
        self.client.force_login(self.admin)

    def test_user_management_page_offers_supported_account_roles(self):
        user = User.objects.create_user(
            username='page_farmer',
            password='UserPass123!',
        )
        user.groups.add(Group.objects.create(name='Applicant'))
        Applicant.objects.create(
            user=user,
            applicant_type='Farmer',
            address='Test address',
            valid_id_type='Government ID',
            valid_id_number='Pending Verification',
        )

        response = self.client.get(reverse('users:user_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add User')
        self.assertContains(response, 'Equipment Officer')
        self.assertContains(response, 'Finance Officer')
        self.assertContains(response, 'Equipment Operator')
        self.assertContains(response, 'Farmer')
        self.assertContains(response, 'data-mode="edit"')
        self.assertContains(response, 'data-bs-target="#deleteUserModal"')
        self.assertContains(response, 'Remove')

    def test_admin_can_create_each_managed_account_type(self):
        roles = (
            'Equipment Officer',
            'Finance Officer',
            'Equipment Operator',
            'Farmer',
        )

        for index, role in enumerate(roles):
            response = self.client.post(reverse('users:user_save_ajax'), {
                'username': f'managed_user_{index}',
                'first_name': 'Test',
                'last_name': 'User',
                'email': f'managed_user_{index}@example.com',
                'password': 'UserPass123!',
                'is_active': 'true',
                'role': role,
            })

            self.assertEqual(response.status_code, 200, response.json())
            user = User.objects.get(username=f'managed_user_{index}')
            expected_group = 'Applicant' if role == 'Farmer' else role
            self.assertTrue(user.groups.filter(name=expected_group).exists())
            self.assertTrue(user.check_password('UserPass123!'))
            self.assertFalse(user.is_staff)
            if role == 'Farmer':
                applicant = Applicant.objects.get(user=user)
                self.assertEqual(applicant.applicant_type, 'Farmer')

    def test_create_requires_a_supported_role(self):
        response = self.client.post(reverse('users:user_save_ajax'), {
            'username': 'invalid_role_user',
            'password': 'UserPass123!',
            'role': 'Admin',
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='invalid_role_user').exists())

    def test_admin_can_edit_user_details_password_status_and_role(self):
        user = User.objects.create_user(
            username='officer_before',
            password='OldPass123!',
            first_name='Old',
            email='old@example.com',
        )
        user.groups.add(Group.objects.create(name='Equipment Officer'))

        response = self.client.post(reverse('users:user_save_ajax'), {
            'id': user.pk,
            'username': 'officer_after',
            'first_name': 'New',
            'last_name': 'Name',
            'email': 'new@example.com',
            'password': 'NewPass123!',
            'is_active': 'false',
            'role': 'Finance Officer',
        })

        self.assertEqual(response.status_code, 200, response.json())
        user.refresh_from_db()
        self.assertEqual(user.username, 'officer_after')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'Name')
        self.assertEqual(user.email, 'new@example.com')
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password('NewPass123!'))
        self.assertTrue(user.groups.filter(name='Finance Officer').exists())
        self.assertFalse(user.groups.filter(name='Equipment Officer').exists())

    def test_admin_can_edit_farmer_profile_information(self):
        user = User.objects.create_user(username='farmer_before', password='UserPass123!')
        user.groups.add(Group.objects.create(name='Applicant'))
        applicant = Applicant.objects.create(
            user=user,
            applicant_type='Farmer',
            organization_name='Old Farm',
            address='Old address',
            valid_id_type='Old ID',
            valid_id_number='OLD-123',
            tin_number='OLD-TIN',
        )

        response = self.client.post(reverse('users:user_save_ajax'), {
            'id': user.pk,
            'username': 'farmer_after',
            'first_name': 'Updated',
            'last_name': 'Farmer',
            'email': 'farmer@example.com',
            'is_active': 'true',
            'role': 'Farmer',
            'applicant_type': 'Cooperative',
            'organization_name': 'New Farm Cooperative',
            'address': 'New address',
            'valid_id_type': 'Philippine National ID',
            'valid_id_number': 'NEW-456',
            'tin_number': 'NEW-TIN',
        })

        self.assertEqual(response.status_code, 200, response.json())
        user.refresh_from_db()
        applicant.refresh_from_db()
        self.assertEqual(user.username, 'farmer_after')
        self.assertEqual(applicant.applicant_type, 'Cooperative')
        self.assertEqual(applicant.organization_name, 'New Farm Cooperative')
        self.assertEqual(applicant.address, 'New address')
        self.assertEqual(applicant.valid_id_type, 'Philippine National ID')
        self.assertEqual(applicant.valid_id_number, 'NEW-456')
        self.assertEqual(applicant.tin_number, 'NEW-TIN')

    def test_edit_requires_a_supported_role(self):
        user = User.objects.create_user(username='editable_user', password='UserPass123!')

        response = self.client.post(reverse('users:user_save_ajax'), {
            'id': user.pk,
            'username': user.username,
            'is_active': 'true',
            'role': 'Admin',
        })

        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.groups.exists())

    def test_remove_deactivates_account_and_preserves_farmer_profile(self):
        user = User.objects.create_user(
            username='farmer_to_remove',
            password='UserPass123!',
        )
        user.groups.add(Group.objects.create(name='Applicant'))
        Applicant.objects.create(
            user=user,
            applicant_type='Farmer',
            address='Test address',
            valid_id_type='Government ID',
            valid_id_number='Pending Verification',
        )

        response = self.client.post(reverse('users:user_delete_ajax', args=[user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'deactivated')
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(Applicant.objects.filter(user=user).exists())

    def test_admin_account_cannot_be_removed(self):
        response = self.client.post(reverse('users:user_delete_ajax', args=[self.admin.pk]))

        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
