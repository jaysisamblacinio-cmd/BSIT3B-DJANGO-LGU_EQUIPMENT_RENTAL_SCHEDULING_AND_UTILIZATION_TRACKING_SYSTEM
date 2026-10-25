from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def get_user_role(user):
    """Determine the effective LGU role for a given user."""
    if not user or not user.is_authenticated:
        return 'Guest'

    if user.is_superuser:
        return 'Admin'

    # Check explicit group membership first
    group_names = set(user.groups.values_list('name', flat=True))
    for role_name in ['Admin', 'Equipment Officer', 'Finance Officer', 'Equipment Operator', 'Applicant']:
        if role_name in group_names:
            return role_name

    # Check if user has an applicant profile
    try:
        from apps.rentals.models import Applicant
        if Applicant.objects.filter(user=user).exists():
            return 'Applicant'
    except Exception:
        pass

    if user.is_staff:
        return 'Equipment Officer'

    return 'Applicant'


def role_required(allowed_roles, redirect_url='dashboard'):
    """Decorator to enforce that the user has at least one of the allowed roles.
    Admins are always permitted.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            role = get_user_role(request.user)
            if role == 'Admin' or role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, f"Access restricted. Your current role ({role}) does not have permission for this section.")
            return redirect(redirect_url)

        return _wrapped_view
    return decorator
