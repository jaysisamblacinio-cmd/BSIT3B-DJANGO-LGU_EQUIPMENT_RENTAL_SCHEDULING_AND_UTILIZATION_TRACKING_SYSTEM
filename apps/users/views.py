from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q


ACCOUNT_ROLES = {
    'Equipment Officer': 'Equipment Officer',
    'Finance Officer': 'Finance Officer',
    'Equipment Operator': 'Equipment Operator',
    'Farmer': 'Applicant',
}


def _is_superuser(user):
    return user.is_superuser


def _management_role(user):
    if user.is_superuser:
        return 'Admin'

    group_names = {group.name for group in user.groups.all()}
    for role_name in ('Admin', 'Equipment Officer', 'Finance Officer', 'Equipment Operator'):
        if role_name in group_names:
            return role_name
    if 'Applicant' in group_names or user.applicant_profile.all():
        return 'Farmer'
    if user.is_staff:
        return 'Equipment Officer'
    return 'Farmer'


# PAGE
@login_required(login_url='login')
@user_passes_test(_is_superuser, login_url='dashboard')
def user_list_page(request):
    query = request.GET.get('q', '').strip()

    users_list = User.objects.all().prefetch_related(
        'groups',
        'applicant_profile',
    ).order_by('-date_joined')

    if query:
        users_list = users_list.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)
    for user in users:
        user.management_role = _management_role(user)

    return render(request, 'users/list.html', {
        'users': users,
        'query': query,
        'managed_roles': tuple(ACCOUNT_ROLES),
    })


# LIST USERS (AJAX)
@login_required(login_url='login')
@user_passes_test(_is_superuser, login_url='dashboard')
def user_list_ajax(request):
    users_list = User.objects.all().order_by('-date_joined')
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)
    data = list(users.object_list.values(
        'id',
        'username',
        'first_name',
        'last_name',
        'email',
        'is_staff',
        'is_active',
        'date_joined',
    ))
    return JsonResponse({
        "data":     data,
        "has_next": users.has_next(),
        "has_prev": users.has_previous(),
        "page":     users.number,
        "pages":    users.paginator.num_pages,
        "total":    users.paginator.count,
    })


# GET SINGLE USER (AJAX)
@login_required(login_url='login')
@user_passes_test(_is_superuser, login_url='dashboard')
def user_get_ajax(request, pk):
    user = get_object_or_404(User, pk=pk)
    applicant = user.applicant_profile.first()
    return JsonResponse({
        "id":         user.id,
        "username":   user.username,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "email":      user.email,
        "is_staff":   user.is_staff,
        "is_active":  user.is_active,
        "role":       _management_role(user),
        "applicant_type": applicant.applicant_type if applicant else "",
        "organization_name": applicant.organization_name if applicant else "",
        "address": applicant.address if applicant else "",
        "valid_id_type": applicant.valid_id_type if applicant else "",
        "valid_id_number": applicant.valid_id_number if applicant else "",
        "tin_number": applicant.tin_number if applicant else "",
    })


# CREATE / UPDATE USER (AJAX)
@login_required(login_url='login')
@user_passes_test(_is_superuser, login_url='dashboard')
@require_POST
def user_save_ajax(request):
    user_id = request.POST.get("id")

    if user_id:
        user = get_object_or_404(User, pk=user_id)
        if user.is_superuser or _management_role(user) == 'Admin':
            return JsonResponse({"error": "Administrator accounts cannot be edited here."}, status=400)
        is_update = True
    else:
        user = User()
        is_update = False

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    role = request.POST.get("role", "").strip()

    if not username:
        return JsonResponse({"error": "Username is required."}, status=400)
    if role not in ACCOUNT_ROLES:
        return JsonResponse({"error": "Choose a valid account type."}, status=400)

    dup_qs = User.objects.filter(Q(username=username) | (Q(email=email) & ~Q(email="")))
    if user_id:
        dup_qs = dup_qs.exclude(pk=user_id)
    if dup_qs.filter(username=username).exists():
        return JsonResponse({"error": "That username is already taken."}, status=400)
    if email and dup_qs.filter(email=email).exists():
        return JsonResponse({"error": "That email is already in use."}, status=400)

    user.username   = username
    user.first_name = request.POST.get("first_name", "")
    user.last_name  = request.POST.get("last_name", "")
    user.email      = email
    user.is_active  = request.POST.get("is_active") == "true"

    password = request.POST.get("password")
    if password:
        user.set_password(password)
    elif not user_id:
        return JsonResponse({"error": "Password is required for new users."}, status=400)

    try:
        with transaction.atomic():
            if not is_update:
                user.is_staff = False
            user.save()

            group_name = ACCOUNT_ROLES[role]
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.set([group])

            if role == 'Farmer':
                from apps.rentals.models import Applicant
                applicant = Applicant.objects.filter(user=user).first()
                if applicant is None:
                    Applicant.objects.create(
                        user=user,
                        applicant_type=request.POST.get('applicant_type', 'Farmer').strip() or 'Farmer',
                        organization_name=request.POST.get('organization_name', '').strip(),
                        address=request.POST.get('address', '').strip() or 'LGU Municipal Jurisdiction',
                        valid_id_type=request.POST.get('valid_id_type', '').strip() or 'Government ID',
                        valid_id_number=request.POST.get('valid_id_number', '').strip() or 'Pending Verification',
                        tin_number=request.POST.get('tin_number', '').strip(),
                    )
                else:
                    applicant.applicant_type = request.POST.get(
                        'applicant_type', applicant.applicant_type
                    ).strip() or applicant.applicant_type
                    applicant.organization_name = request.POST.get(
                        'organization_name', applicant.organization_name or ''
                    ).strip()
                    applicant.address = request.POST.get(
                        'address', applicant.address
                    ).strip() or applicant.address
                    applicant.valid_id_type = request.POST.get(
                        'valid_id_type', applicant.valid_id_type
                    ).strip() or applicant.valid_id_type
                    applicant.valid_id_number = request.POST.get(
                        'valid_id_number', applicant.valid_id_number
                    ).strip() or applicant.valid_id_number
                    applicant.tin_number = request.POST.get(
                        'tin_number', applicant.tin_number or ''
                    ).strip()
                    applicant.save()
    except IntegrityError:
        return JsonResponse({"error": "Could not save user due to a conflict (duplicate username/email)."}, status=400)

    messages.success(
        request,
        f'User "{user.username}" has been {"updated" if is_update else "saved"} successfully.'
    )

    return JsonResponse({
        "status": "success",
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "role": _management_role(user),
    })


# DELETE USER (AJAX)
@login_required(login_url='login')
@user_passes_test(_is_superuser, login_url='dashboard')
@require_POST
def user_delete_ajax(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.user == user:
        return JsonResponse({"error": "You cannot remove your own account."}, status=400)
    if user.is_superuser or _management_role(user) not in ACCOUNT_ROLES:
        return JsonResponse({"error": "Only officer, finance, operator, and farmer accounts can be removed here."}, status=400)
    if not user.is_active:
        return JsonResponse({"error": "This account is already inactive."}, status=400)

    username = user.username
    user.is_active = False
    user.save(update_fields=['is_active'])
    return JsonResponse({
        "status": "deactivated",
        "message": f'User "{username}" has been deactivated. Account access is disabled and history is preserved.',
    })