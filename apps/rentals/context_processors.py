from .permissions import get_user_role


def lgu_context(request):
    if not request.user.is_authenticated:
        return {
            'user_role': 'Guest',
            'is_admin': False,
            'is_officer': False,
            'is_finance': False,
            'is_operator': False,
            'is_applicant': False,
            'unread_notifications_count': 0,
            'pending_requests_count': 0,
        }

    role = get_user_role(request.user)

    unread_count = 0
    pending_count = 0

    try:
        from apps.rentals.models import Notification, RentalRequest
        unread_count = Notification.objects.filter(user=request.user, is_read=0).count()
        if role in ['Admin', 'Equipment Officer']:
            pending_count = RentalRequest.objects.filter(status='Pending').count()
    except Exception:
        pass

    return {
        'user_role': role,
        'is_admin': (role == 'Admin'),
        'is_officer': (role in ['Admin', 'Equipment Officer']),
        'is_finance': (role in ['Admin', 'Finance Officer']),
        'is_operator': (role in ['Admin', 'Equipment Operator']),
        'is_applicant': (role == 'Applicant'),
        'unread_notifications_count': unread_count,
        'pending_requests_count': pending_count,
        'demo_accounts': [
            {'username': 'ADMIN12', 'role': 'Admin', 'desc': 'System Administrator'},
            {'username': 'glenn', 'role': 'Admin', 'desc': 'LGU Administrator'},
            {'username': 'officer', 'role': 'Equipment Officer', 'desc': 'Machinery & Review'},
            {'username': 'finance', 'role': 'Finance Officer', 'desc': 'Payments & ORs'},
            {'username': 'danilo_operator', 'role': 'Equipment Operator', 'desc': 'Engine Hours & Fuel'},
            {'username': 'farmer_juan', 'role': 'Applicant (Farmer)', 'desc': 'Cooperative Member'},
            {'username': 'contractor_mateo', 'role': 'Applicant (Contractor)', 'desc': 'PCAB Licensed'},
        ]
    }
